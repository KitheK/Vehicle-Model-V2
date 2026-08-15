#ifndef AXLE_CAR_6DOF_FSAE_HPP
#define AXLE_CAR_6DOF_FSAE_HPP

#include "src/core/foundation/fastest_lap_exception.h"

template<typename Timeseries_t, typename Tire_left_t, typename Tire_right_t, template<size_t,size_t> typename Axle_mode, size_t state_start, size_t control_start>
Axle_car_6dof_fsae<Timeseries_t,Tire_left_t,Tire_right_t,Axle_mode,state_start,control_start>::Axle_car_6dof_fsae(
    const std::string& name, const Tire_left_t& tire_l, const Tire_right_t& tire_r, const std::string& path)
: Axle<Timeseries_t,std::tuple<Tire_left_t,Tire_right_t>,state_start,control_start>(name, {tire_l, tire_r}),
  _engine(),
  _brakes()
{
    base_type::_path = path;
    _y_tire = {-0.5*_track, 0.5*_track};

    std::get<LEFT>(base_type::_tires).get_frame().add_rotation(0.0, 0.0, Z);
    std::get<RIGHT>(base_type::_tires).get_frame().add_rotation(0.0, 0.0, Z);
    std::get<LEFT>(base_type::_tires).get_frame().add_rotation(0.0, 0.0, X);
    std::get<RIGHT>(base_type::_tires).get_frame().add_rotation(0.0, 0.0, X);

    std::get<LEFT>(base_type::_tires).get_frame().set_origin(get_tire_position(LEFT), get_tire_velocity(LEFT), Frame<Timeseries_t>::Frame_velocity_types::parent_frame);
    std::get<RIGHT>(base_type::_tires).get_frame().set_origin(get_tire_position(RIGHT), get_tire_velocity(RIGHT), Frame<Timeseries_t>::Frame_velocity_types::parent_frame);
}

template<typename Timeseries_t, typename Tire_left_t, typename Tire_right_t, template<size_t,size_t> typename Axle_mode, size_t state_start, size_t control_start>
Axle_car_6dof_fsae<Timeseries_t,Tire_left_t,Tire_right_t,Axle_mode,state_start,control_start>::Axle_car_6dof_fsae(
    const std::string& name, const Tire_left_t& tire_l, const Tire_right_t& tire_r, Xml_document& database, const std::string& path)
: Axle<Timeseries_t,std::tuple<Tire_left_t,Tire_right_t>,state_start,control_start>(name, {tire_l, tire_r}),
  _engine(),
  _brakes()
{
    base_type::_path = path;

    read_parameters(database, path, get_parameters(), __used_parameters);
    _y_tire = {-0.5*_track, 0.5*_track};

    if (database.has_element(path + "brakes/"))
        _brakes = Brake<Timeseries_t>(database, path + "brakes/");

    if constexpr (std::is_same<Axle_mode<0,0>, POWERED_WITH_DIFFERENTIAL<0,0>>::value)
    {
        if (database.has_element(path + "engine/"))
            _engine = Engine<Timeseries_t>(database, path + "engine/", true);
    }

    if constexpr (std::is_same<Axle_mode<0,0>, STEERING_WITH_KAPPA<0,0>>::value)
    {
        if (std::get<LEFT>(base_type::_tires).get_frame().get_rotation_angles().size() != 0)
            throw fastest_lap_exception("Left tire frame must have zero rotations");
        if (std::get<RIGHT>(base_type::_tires).get_frame().get_rotation_angles().size() != 0)
            throw fastest_lap_exception("Right tire frame must have zero rotations");

        std::get<LEFT>(base_type::_tires).get_frame().add_rotation(0.0, 0.0, Z);
        std::get<RIGHT>(base_type::_tires).get_frame().add_rotation(0.0, 0.0, Z);
    }
    else
    {
        std::get<LEFT>(base_type::_tires).get_frame().add_rotation(0.0, 0.0, Z);
        std::get<RIGHT>(base_type::_tires).get_frame().add_rotation(0.0, 0.0, Z);
    }
    std::get<LEFT>(base_type::_tires).get_frame().add_rotation(0.0, 0.0, X);
    std::get<RIGHT>(base_type::_tires).get_frame().add_rotation(0.0, 0.0, X);

    std::get<LEFT>(base_type::_tires).get_frame().set_origin(get_tire_position(LEFT), get_tire_velocity(LEFT), Frame<Timeseries_t>::Frame_velocity_types::parent_frame);
    std::get<RIGHT>(base_type::_tires).get_frame().set_origin(get_tire_position(RIGHT), get_tire_velocity(RIGHT), Frame<Timeseries_t>::Frame_velocity_types::parent_frame);
}

template<typename Timeseries_t, typename Tire_left_t, typename Tire_right_t, template<size_t,size_t> typename Axle_mode, size_t state_start, size_t control_start>
template<size_t number_of_inputs, size_t number_of_controls>
void Axle_car_6dof_fsae<Timeseries_t,Tire_left_t,Tire_right_t,Axle_mode,state_start,control_start>::transform_states_to_inputs(
    const std::array<Timeseries_t,number_of_inputs>&, const std::array<Timeseries_t,number_of_controls>& controls,
    std::array<Timeseries_t,number_of_inputs>&)
{
    if constexpr (std::is_same<Axle_mode<0,0>,STEERING_WITH_KAPPA<0,0>>::value)
    {
        const auto& delta = controls[control_names::STEERING];
        std::get<LEFT>(base_type::_tires).get_frame().set_rotation_angle(0,delta);
        std::get<RIGHT>(base_type::_tires).get_frame().set_rotation_angle(0,delta);
    }
}

template<typename Timeseries_t, typename Tire_left_t, typename Tire_right_t, template<size_t,size_t> typename Axle_mode, size_t state_start, size_t control_start>
void Axle_car_6dof_fsae<Timeseries_t,Tire_left_t,Tire_right_t,Axle_mode,state_start,control_start>::update(
    const Vector3d<Timeseries_t>& x0, const Vector3d<Timeseries_t>& v0, Timeseries_t phi, Timeseries_t dphi,
    Timeseries_t throttle, Timeseries_t brake_bias, const Frame<Timeseries_t>& road_frame,
    Timeseries_t grip_left, Timeseries_t grip_right)
{
    base_type::get_frame().set_origin(x0, v0, Frame<Timeseries_t>::Frame_velocity_types::parent_frame);

    Tire_left_t& tire_l  = std::get<LEFT>(base_type::_tires);
    Tire_right_t& tire_r = std::get<RIGHT>(base_type::_tires);

    _phi = phi;
    _dphi = dphi;

    _camber[LEFT]  = _camber_static + _camber_gain_roll * phi;
    _camber[RIGHT] = _camber_static - _camber_gain_roll * phi;
    _toe[LEFT]  = _toe_static + _toe_gain_roll * phi;
    _toe[RIGHT] = _toe_static - _toe_gain_roll * phi;

    Timeseries_t delta_left = _toe[LEFT];
    Timeseries_t delta_right = _toe[RIGHT];
    if constexpr (std::is_same<Axle_mode<0,0>, STEERING_WITH_KAPPA<0,0>>::value)
    {
        delta_left += _delta;
        delta_right += _delta;
    }
    std::get<LEFT>(base_type::_tires).get_frame().set_rotation_angle(0, delta_left);
    std::get<RIGHT>(base_type::_tires).get_frame().set_rotation_angle(0, delta_right);
    std::get<LEFT>(base_type::_tires).get_frame().set_rotation_angle(1, _camber[LEFT]);
    std::get<RIGHT>(base_type::_tires).get_frame().set_rotation_angle(1, _camber[RIGHT]);

    const scalar& k_tire = tire_l.get_radial_stiffness();
    const scalar& R0     = tire_l.get_radius();

    Timeseries_t displ_symmetric  = base_type::get_frame().get_absolute_position().at(Z)+R0;
    Timeseries_t ddispl_symmetric = base_type::get_frame().get_absolute_velocity_in_inertial().at(Z);

    Timeseries_t displ_assymmetric  = 0.5*_track*phi;
    Timeseries_t ddispl_assymmetric = 0.5*_track*dphi;

    if constexpr (std::is_same<Axle_mode<0,0>, STEERING_WITH_KAPPA<0,0>>::value)
        displ_assymmetric += _beta[RIGHT]*_delta;

    const scalar sym_stiffness = 1.0/(_k_wheel + k_tire);
    const scalar assym_stiffness = 2.0*_k_antiroll*k_tire*sym_stiffness/(2.0*_k_antiroll + _k_wheel + k_tire);

    const Timeseries_t wl = _k_wheel*sym_stiffness*(displ_symmetric - displ_assymmetric)
                           -displ_assymmetric*assym_stiffness;
    const Timeseries_t wr = _k_wheel*sym_stiffness*(displ_symmetric + displ_assymmetric)
                          +displ_assymmetric*assym_stiffness;

    const Timeseries_t dwl = _k_wheel*sym_stiffness*(ddispl_symmetric - ddispl_assymmetric)
                           -assym_stiffness*ddispl_assymmetric;
    const Timeseries_t dwr = _k_wheel*sym_stiffness*(ddispl_symmetric + ddispl_assymmetric)
                          +assym_stiffness*ddispl_assymmetric;

    _s[LEFT]  = wl - displ_symmetric + displ_assymmetric;
    _s[RIGHT] = wr - displ_symmetric - displ_assymmetric;
    _ds[LEFT]  = dwl - ddispl_symmetric + ddispl_assymmetric;
    _ds[RIGHT] = dwr - ddispl_symmetric - ddispl_assymmetric;

    const Timeseries_t Fz_left  = smooth_pos(k_tire*wl + _c_damper*_ds[LEFT], 1.0);
    const Timeseries_t Fz_right = smooth_pos(k_tire*wr + _c_damper*_ds[RIGHT], 1.0);

    tire_l.get_frame().set_origin(get_tire_position(LEFT), get_tire_velocity(LEFT), Frame<Timeseries_t>::Frame_velocity_types::parent_frame);
    tire_r.get_frame().set_origin(get_tire_position(RIGHT), get_tire_velocity(RIGHT), Frame<Timeseries_t>::Frame_velocity_types::parent_frame);

    tire_l.update(Fz_left, _kappa_dimensionless_left, road_frame);
    tire_r.update(Fz_right, _kappa_dimensionless_right, road_frame);
    tire_l.scale_xy_forces(grip_left);
    tire_r.scale_xy_forces(grip_right);

    const Timeseries_t& omega_left = tire_l.get_omega();
    const Timeseries_t& omega_right = tire_r.get_omega();

    const Timeseries_t brake_percentage = smooth_pos(-throttle, _throttle_smooth_pos);

    _torque_left  = -smooth_sign(omega_left,1.0)*_brakes(brake_percentage)*brake_bias;
    _torque_right = -smooth_sign(omega_right,1.0)*_brakes(brake_percentage)*brake_bias;

    if constexpr (std::is_same<Axle_mode<0,0>, POWERED_WITH_DIFFERENTIAL<0,0>>::value)
    {
        const Timeseries_t motor_command = smooth_pos(throttle, _throttle_smooth_pos)
                                         - _regen_coefficient * smooth_pos(-throttle, _throttle_smooth_pos);
        const Timeseries_t engine_torque = _engine(motor_command, 0.5*(omega_left + omega_right));
        const Timeseries_t differential_torque = _differential_stiffness*(omega_left - omega_right);
        _torque_left  += 0.5*engine_torque - differential_torque;
        _torque_right += 0.5*engine_torque + differential_torque;
    }

    _dangular_momentum_dt_left  = (_torque_left  + tire_l.get_longitudinal_torque_at_wheel_center());
    _dangular_momentum_dt_right = (_torque_right + tire_r.get_longitudinal_torque_at_wheel_center());

    const Vector3d<Timeseries_t> F_left = tire_l.get_force_in_parent();
    const Vector3d<Timeseries_t> F_right = tire_r.get_force_in_parent();
    const Vector3d<Timeseries_t> T_left = tire_l.get_torque_in_parent();
    const Vector3d<Timeseries_t> T_right = tire_r.get_torque_in_parent();

    base_type::_F = F_left + F_right;
    base_type::_T =  T_left  + cross(tire_l.get_frame().get_origin(), F_left)
                   + T_right + cross(tire_r.get_frame().get_origin(), F_right);
}

template<typename Timeseries_t, typename Tire_left_t, typename Tire_right_t, template<size_t,size_t> typename Axle_mode, size_t state_start, size_t control_start>
template<size_t number_of_states>
void Axle_car_6dof_fsae<Timeseries_t,Tire_left_t,Tire_right_t,Axle_mode,state_start,control_start>::get_state_and_state_derivative(
    std::array<Timeseries_t,number_of_states>& state, std::array<Timeseries_t, number_of_states>& dstate_dt, const Timeseries_t& mass_kg) const
{
    base_type::get_state_and_state_derivative(state, dstate_dt);

    const auto scaling_factor = (_I < 1.0e-10 ? 1.0/mass_kg : 1.0);

    state    [state_names::angular_momentum_left] = std::get<0>(base_type::_tires).get_omega() * _I * scaling_factor;
    dstate_dt[state_names::angular_momentum_left] = _dangular_momentum_dt_left * scaling_factor;
    state    [state_names::angular_momentum_right] = std::get<1>(base_type::_tires).get_omega() * _I * scaling_factor;
    dstate_dt[state_names::angular_momentum_right] = _dangular_momentum_dt_right * scaling_factor;
}

template<typename Timeseries_t, typename Tire_left_t, typename Tire_right_t, template<size_t,size_t> typename Axle_mode, size_t state_start, size_t control_start>
template<size_t number_of_inputs, size_t number_of_controls>
void Axle_car_6dof_fsae<Timeseries_t,Tire_left_t,Tire_right_t,Axle_mode,state_start,control_start>::set_state_and_control_names(
    std::array<std::string,number_of_inputs>& inputs, std::array<std::string,number_of_controls>& controls) const
{
    base_type::set_state_and_control_names(inputs, controls);

    inputs[input_names::KAPPA_LEFT]  = base_type::_name + ".left-tire.kappa";
    inputs[input_names::KAPPA_RIGHT] = base_type::_name + ".right-tire.kappa";

    if constexpr (std::is_same<Axle_mode<0,0>,STEERING_WITH_KAPPA<0,0>>::value)
        controls[control_names::STEERING] = base_type::_name + ".steering-angle";
}

template<typename Timeseries_t, typename Tire_left_t, typename Tire_right_t, template<size_t,size_t> typename Axle_mode, size_t state_start, size_t control_start>
template<size_t number_of_inputs, size_t number_of_controls>
void Axle_car_6dof_fsae<Timeseries_t,Tire_left_t,Tire_right_t,Axle_mode,state_start,control_start>::set_state_and_controls(
    const std::array<Timeseries_t,number_of_inputs>& inputs, const std::array<Timeseries_t,number_of_controls>& controls)
{
    base_type::set_state_and_controls(inputs, controls);

    _kappa_dimensionless_left  = inputs[input_names::KAPPA_LEFT];
    _kappa_dimensionless_right = inputs[input_names::KAPPA_RIGHT];

    if constexpr (std::is_same<Axle_mode<0,0>,STEERING_WITH_KAPPA<0,0>>::value)
    {
        _delta = controls[control_names::STEERING];
        std::get<LEFT>(base_type::_tires).get_frame().set_rotation_angle(0,_delta);
        std::get<RIGHT>(base_type::_tires).get_frame().set_rotation_angle(0,_delta);
    }
}

template<typename Timeseries_t, typename Tire_left_t, typename Tire_right_t, template<size_t,size_t> typename Axle_mode, size_t state_start, size_t control_start>
template<size_t number_of_inputs, size_t number_of_controls>
void Axle_car_6dof_fsae<Timeseries_t,Tire_left_t,Tire_right_t,Axle_mode,state_start,control_start>::set_state_and_control_upper_lower_and_default_values(
    std::array<scalar,number_of_inputs>& inputs_def, std::array<scalar,number_of_inputs>& inputs_lb, std::array<scalar,number_of_inputs>& inputs_ub,
    std::array<scalar,number_of_controls>& controls_def, std::array<scalar,number_of_controls>& controls_lb, std::array<scalar,number_of_controls>& controls_ub) const
{
    base_type::set_state_and_control_upper_lower_and_default_values(inputs_def,inputs_lb,inputs_ub,controls_def,controls_lb,controls_ub);

    inputs_def[input_names::KAPPA_LEFT] = 0.0;
    inputs_lb[input_names::KAPPA_LEFT]  = -1.0;
    inputs_ub[input_names::KAPPA_LEFT]  =  1.0;
    inputs_def[input_names::KAPPA_RIGHT] = 0.0;
    inputs_lb[input_names::KAPPA_RIGHT]  = -1.0;
    inputs_ub[input_names::KAPPA_RIGHT]  =  1.0;

    if constexpr (std::is_same_v<Axle_mode<0,0>,STEERING_WITH_KAPPA<0,0>>)
    {
        controls_def[control_names::STEERING] = 0.0;
        controls_lb[control_names::STEERING] = -20.0*DEG;
        controls_ub[control_names::STEERING] =  20.0*DEG;
    }
}

#endif
