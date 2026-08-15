#ifndef CHASSIS_CAR_6DOF_FSAE_HPP
#define CHASSIS_CAR_6DOF_FSAE_HPP

#include <array>

template<typename Timeseries_t, typename FrontAxle_t, typename RearAxle_t, size_t state_start, size_t control_start>
inline void Chassis_car_6dof_fsae<Timeseries_t,FrontAxle_t,RearAxle_t,state_start,control_start>::update(
    const Vector3d<Timeseries_t>& ground_position_vector_m,
    const Euler_angles<scalar>& road_euler_angles_rad,
    const Timeseries_t& track_heading_angle_rad,
    const Euler_angles<Timeseries_t>& road_euler_angles_dot_radps,
    const Timeseries_t& track_heading_angle_dot_radps,
    const Timeseries_t& ground_velocity_z_body_mps)
{
    base_type::base_type::update(ground_position_vector_m, road_euler_angles_rad, track_heading_angle_rad,
                                 road_euler_angles_dot_radps, track_heading_angle_dot_radps, ground_velocity_z_body_mps);

    auto& front_axle = this->get_front_axle();
    auto& rear_axle  = this->get_rear_axle();
    auto& road_frame = this->get_road_frame();
    const auto& m = this->get_mass();

    this->get_chassis_frame().set_origin(this->get_com_position(), this->get_com_velocity(), Frame<Timeseries_t>::Frame_velocity_types::parent_frame);

    const Timeseries_t grip_fl = grip_scale_from_temperature(_tire_temperature[0]);
    const Timeseries_t grip_fr = grip_scale_from_temperature(_tire_temperature[1]);
    const Timeseries_t grip_rl = grip_scale_from_temperature(_tire_temperature[2]);
    const Timeseries_t grip_rr = grip_scale_from_temperature(_tire_temperature[3]);

    front_axle.update(this->get_front_axle_position(), this->get_front_axle_velocity(), this->_phi, this->_dphi,
                      _throttle, _brake_bias, road_frame, grip_fl, grip_fr);
    rear_axle.update(this->get_rear_axle_position(), this->get_rear_axle_velocity(), this->_phi, this->_dphi,
                     _throttle, 1.0 - _brake_bias, road_frame, grip_rl, grip_rr);

    const Matrix3x3<Timeseries_t> Q_front = front_axle.get_frame().get_rotation_matrix(road_frame);
    const Matrix3x3<Timeseries_t> Q_rear  = rear_axle.get_frame().get_rotation_matrix(road_frame);

    const Vector3d<Timeseries_t> x_front = std::get<0>(front_axle.get_frame().get_position_and_velocity_in_target(road_frame));
    const Vector3d<Timeseries_t> x_rear  = std::get<0>(rear_axle.get_frame().get_position_and_velocity_in_target(road_frame));

    const Vector3d<Timeseries_t> F_front = Q_front*front_axle.get_force();
    const Vector3d<Timeseries_t> F_rear  = Q_rear*rear_axle.get_force();
    const Vector3d<Timeseries_t> T_front = Q_front*front_axle.get_torque();
    const Vector3d<Timeseries_t> T_rear  = Q_rear*rear_axle.get_torque();

    this->_total_force_N = F_front + F_rear;
    this->_total_force_N[Z] += m*g0;

    this->_total_torque_Nm = T_front + cross(x_front, F_front) + T_rear + cross(x_rear, F_rear);

    const auto aerodynamic_forces = this->get_aerodynamic_force();
    _cl_scale = 1.0 + _dCl_dz * this->_z + _dCl_dmu * this->_mu;
    _cd_scale = 1.0 + _dCd_dz * this->_z + _dCd_dmu * this->_mu;
    _cl_scale = max(Timeseries_t(0.2), min(Timeseries_t(3.0), _cl_scale));
    _cd_scale = max(Timeseries_t(0.2), min(Timeseries_t(3.0), _cd_scale));

    const auto F_aero = aerodynamic_forces.lift * _cl_scale + aerodynamic_forces.drag * _cd_scale;
    this->_total_force_N += F_aero;
    this->_total_torque_Nm += cross(_x_aero + Vector3d<Timeseries_t>(0.0, 0.0, this->_z), F_aero);

    const scalar wheelbase = this->_x_front_axle.x() - this->_x_rear_axle.x();
    _front_aero_distribution = (_x_aero.x() - this->_x_rear_axle.x()) / wheelbase;

    const Vector3d<Timeseries_t> dvdt = -this->Newton_lhs() + this->_total_force_N/m;

    this->_com_velocity_x_mps = this->get_u();
    this->_com_velocity_y_mps = this->get_v();
    this->_com_velocity_x_dot_mps2 = dvdt[X];
    this->_com_velocity_y_dot_mps2 = dvdt[Y];
    this->_d2z = dvdt[Z];

    const Vector3d<Timeseries_t> d2phi = linsolve(this->Euler_m(), -this->Euler_lhs() + this->_total_torque_Nm);
    this->_d2phi = d2phi[X];
    this->_d2mu  = d2phi[Y];
    this->_yaw_rate_dot_radps2 = d2phi[Z];

    const std::array<Timeseries_t,4> dissipation = {
        sqrt(front_axle.template get_tire<0>().get_dissipation()*front_axle.template get_tire<0>().get_dissipation() + 1.0e-24),
        sqrt(front_axle.template get_tire<1>().get_dissipation()*front_axle.template get_tire<1>().get_dissipation() + 1.0e-24),
        sqrt(rear_axle.template get_tire<0>().get_dissipation()*rear_axle.template get_tire<0>().get_dissipation() + 1.0e-24),
        sqrt(rear_axle.template get_tire<1>().get_dissipation()*rear_axle.template get_tire<1>().get_dissipation() + 1.0e-24)
    };
    for (size_t i = 0; i < 4; ++i)
        _tire_temperature_dot[i] = (dissipation[i] - _thermal_cooling * (_tire_temperature[i] - _t_ambient)) / _thermal_capacity;
}

template<typename Timeseries_t, typename FrontAxle_t, typename RearAxle_t, size_t state_start, size_t control_start>
template<size_t number_of_inputs, size_t number_of_controls>
void Chassis_car_6dof_fsae<Timeseries_t,FrontAxle_t,RearAxle_t,state_start,control_start>::set_state_and_control_names(
    std::array<std::string, number_of_inputs>& inputs, std::array<std::string, number_of_controls>& controls) const
{
    base_type::set_state_and_control_names(inputs, controls);
    controls[control_names::throttle] = "chassis.throttle";
    controls[control_names::brake_bias] = "chassis.brake-bias";
    inputs[input_names::T_FL] = "chassis.tire.temperature.fl";
    inputs[input_names::T_FR] = "chassis.tire.temperature.fr";
    inputs[input_names::T_RL] = "chassis.tire.temperature.rl";
    inputs[input_names::T_RR] = "chassis.tire.temperature.rr";
}

template<typename Timeseries_t, typename FrontAxle_t, typename RearAxle_t, size_t state_start, size_t control_start>
template<size_t number_of_inputs, size_t number_of_controls>
void Chassis_car_6dof_fsae<Timeseries_t,FrontAxle_t,RearAxle_t,state_start,control_start>::set_state_and_controls(
    const std::array<Timeseries_t,number_of_inputs>& inputs, const std::array<Timeseries_t,number_of_controls>& controls)
{
    base_type::set_state_and_controls(inputs, controls);
    _throttle   = controls[control_names::throttle];
    _brake_bias = controls[control_names::brake_bias];
    _tire_temperature[0] = inputs[input_names::T_FL];
    _tire_temperature[1] = inputs[input_names::T_FR];
    _tire_temperature[2] = inputs[input_names::T_RL];
    _tire_temperature[3] = inputs[input_names::T_RR];
}

template<typename Timeseries_t, typename FrontAxle_t, typename RearAxle_t, size_t state_start, size_t control_start>
template<size_t number_of_inputs, size_t number_of_controls>
void Chassis_car_6dof_fsae<Timeseries_t,FrontAxle_t,RearAxle_t,state_start,control_start>::set_state_and_control_upper_lower_and_default_values(
    std::array<scalar, number_of_inputs>& inputs_def, std::array<scalar, number_of_inputs>& inputs_lb,
    std::array<scalar, number_of_inputs>& inputs_ub,
    std::array<scalar, number_of_controls>& controls_def, std::array<scalar, number_of_controls>& controls_lb,
    std::array<scalar, number_of_controls>& controls_ub) const
{
    base_type::set_state_and_control_upper_lower_and_default_values(
        inputs_def, inputs_lb, inputs_ub, controls_def, controls_lb, controls_ub);

    controls_def[control_names::throttle] = 0.0;
    controls_lb[control_names::throttle]  = -1.0;
    controls_ub[control_names::throttle]  =  1.0;

    controls_def[control_names::brake_bias] = Value(_brake_bias_0);
    controls_lb[control_names::brake_bias]  = 0.0;
    controls_ub[control_names::brake_bias]  = 1.0;

    // Wheel radius is larger than the kart default used by Chassis_car_6dof.
    inputs_ub[input_names::Z] = 0.21;

    inputs_def[input_names::T_FL] = _t_ambient;
    inputs_def[input_names::T_FR] = _t_ambient;
    inputs_def[input_names::T_RL] = _t_ambient;
    inputs_def[input_names::T_RR] = _t_ambient;
    inputs_lb[input_names::T_FL] = 250.0;
    inputs_lb[input_names::T_FR] = 250.0;
    inputs_lb[input_names::T_RL] = 250.0;
    inputs_lb[input_names::T_RR] = 250.0;
    inputs_ub[input_names::T_FL] = 420.0;
    inputs_ub[input_names::T_FR] = 420.0;
    inputs_ub[input_names::T_RL] = 420.0;
    inputs_ub[input_names::T_RR] = 420.0;
}

template<typename Timeseries_t, typename FrontAxle_t, typename RearAxle_t, size_t state_start, size_t control_start>
template<size_t number_of_states>
void Chassis_car_6dof_fsae<Timeseries_t,FrontAxle_t,RearAxle_t,state_start,control_start>::get_state_and_state_derivative(
    std::array<Timeseries_t, number_of_states>& state,
    std::array<Timeseries_t, number_of_states>& dstate_dt) const
{
    base_type::get_state_and_state_derivative(state, dstate_dt);
    state[state_names::T_FL] = _tire_temperature[0];
    state[state_names::T_FR] = _tire_temperature[1];
    state[state_names::T_RL] = _tire_temperature[2];
    state[state_names::T_RR] = _tire_temperature[3];
    dstate_dt[state_names::T_FL] = _tire_temperature_dot[0];
    dstate_dt[state_names::T_FR] = _tire_temperature_dot[1];
    dstate_dt[state_names::T_RL] = _tire_temperature_dot[2];
    dstate_dt[state_names::T_RR] = _tire_temperature_dot[3];
}

template<typename Timeseries_t, typename FrontAxle_t, typename RearAxle_t, size_t state_start, size_t control_start>
Timeseries_t Chassis_car_6dof_fsae<Timeseries_t,FrontAxle_t,RearAxle_t,state_start,control_start>::grip_scale_from_temperature(
    const Timeseries_t& temperature) const
{
    const Timeseries_t dt = (temperature - _t_optimal) / _t_optimal;
    const Timeseries_t scale = 1.0 - _grip_sensitivity * dt * dt;
    return max(Timeseries_t(0.5), min(Timeseries_t(1.1), scale));
}

#endif
