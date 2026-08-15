#ifndef AXLE_CAR_6DOF_FSAE_H
#define AXLE_CAR_6DOF_FSAE_H

#include "axle.h"
#include "src/core/actuators/engine.h"
#include "src/core/actuators/brake.h"
#include "lion/io/Xml_document.h"
#include "lion/io/database_parameters.h"
#include <algorithm>

//! Powered axle with independent wheel slips and a viscous limited-slip differential.
template<size_t state_start, size_t control_start>
struct POWERED_WITH_DIFFERENTIAL
{
    struct input_names
    {
        enum
        {
            KAPPA_LEFT = state_start,
            KAPPA_RIGHT,
            end
        };
    };

    struct state_names
    {
        enum
        {
            angular_momentum_left = state_start,
            angular_momentum_right,
            end
        };
    };

    static_assert(static_cast<size_t>(input_names::end) == static_cast<size_t>(state_names::end));

    struct control_names
    {
        enum { end = control_start };
    };
};

//! Steering axle with independent wheel slips (front brakes, no engine).
template<size_t state_start, size_t control_start>
struct STEERING_WITH_KAPPA
{
    struct input_names
    {
        enum
        {
            KAPPA_LEFT = state_start,
            KAPPA_RIGHT,
            end
        };
    };

    struct state_names
    {
        enum
        {
            angular_momentum_left = state_start,
            angular_momentum_right,
            end
        };
    };

    static_assert(static_cast<size_t>(input_names::end) == static_cast<size_t>(state_names::end));

    struct control_names
    {
        enum
        {
            STEERING = control_start,
            end
        };
    };
};

//! 6DOF car axle: kart-style vertical spring network + damper + F1-style per-wheel kappa.
template<typename Timeseries_t, typename Tire_left_t, typename Tire_right_t, template<size_t,size_t> typename Axle_mode, size_t state_start, size_t control_start>
class Axle_car_6dof_fsae : public Axle<Timeseries_t,std::tuple<Tire_left_t,Tire_right_t>,state_start,control_start>,
    public Axle_mode<Axle<Timeseries_t,std::tuple<Tire_left_t,Tire_right_t>,state_start,control_start>::input_names::end,
                     Axle<Timeseries_t,std::tuple<Tire_left_t,Tire_right_t>,state_start,control_start>::control_names::end>
{
 public:
    using base_type = Axle<Timeseries_t,std::tuple<Tire_left_t,Tire_right_t>,state_start,control_start>;
    using Axle_type = Axle_mode<Axle<Timeseries_t,std::tuple<Tire_left_t,Tire_right_t>,state_start,control_start>::input_names::end,
                                Axle<Timeseries_t,std::tuple<Tire_left_t,Tire_right_t>,state_start,control_start>::control_names::end>;

    struct input_names : public Axle_type::input_names, base_type::input_names
    {
        constexpr const static size_t end = Axle_type::input_names::end;
    };

    struct control_names : public Axle_type::control_names, base_type::control_names
    {
        constexpr const static size_t end = Axle_type::control_names::end;
    };

    struct state_names : public Axle_type::state_names, base_type::state_names
    {
        constexpr const static size_t end = Axle_type::state_names::end;
    };

    static_assert(static_cast<size_t>(input_names::end) == static_cast<size_t>(state_names::end));

    using Tire_left_type  = Tire_left_t;
    using Tire_right_type = Tire_right_t;

    enum Tires : size_t { LEFT, RIGHT };

    Axle_car_6dof_fsae() = default;

    Axle_car_6dof_fsae(const std::string& name,
             const Tire_left_t& tire_l,
             const Tire_right_t& tire_r,
             const std::string& path="");

    Axle_car_6dof_fsae(const std::string& name,
             const Tire_left_t& tire_l,
             const Tire_right_t& tire_r,
             Xml_document& database,
             const std::string& path="");

    template<size_t number_of_inputs, size_t number_of_controls>
    void transform_states_to_inputs(const std::array<Timeseries_t,number_of_inputs>& states,
                                          const std::array<Timeseries_t,number_of_controls>& controls,
                                          std::array<Timeseries_t,number_of_inputs>& inputs);

    void update(const Vector3d<Timeseries_t>& x0, const Vector3d<Timeseries_t>& v0, Timeseries_t phi, Timeseries_t dphi,
                Timeseries_t throttle, Timeseries_t brake_bias, const Frame<Timeseries_t>& road_frame,
                Timeseries_t grip_left, Timeseries_t grip_right);

    const Timeseries_t& get_steering_angle() const { return _delta; }
    const Timeseries_t& get_camber_left() const { return _camber[LEFT]; }
    const Timeseries_t& get_camber_right() const { return _camber[RIGHT]; }
    const Timeseries_t& get_toe_left() const { return _toe[LEFT]; }
    const Timeseries_t& get_toe_right() const { return _toe[RIGHT]; }
    const Timeseries_t& get_dangular_momentum_dt_left() const { return _dangular_momentum_dt_left; }
    const Timeseries_t& get_dangular_momentum_dt_right() const { return _dangular_momentum_dt_right; }

    const Engine<Timeseries_t>& get_engine() const { return _engine; }

    const Vector3d<Timeseries_t> get_tire_position(Tires tire) const {
                        return {0.0, _y_tire[tire], _s[tire] + _phi*_y_tire[tire] + _beta[tire]*_delta }; }

    const scalar get_tire_y_position(Tires tire) const { return _y_tire[tire]; }

    const Vector3d<Timeseries_t> get_tire_velocity(Tires tire) const {
                        return {0.0, 0.0, _ds[tire] + _dphi*_y_tire[tire]  }; }

    const scalar& get_track() const { return _track; }

    template<size_t number_of_states>
    void get_state_and_state_derivative(std::array<Timeseries_t,number_of_states>& state, std::array<Timeseries_t, number_of_states>& dstate_dt, const Timeseries_t& mass_kg) const;

    template<size_t number_of_inputs, size_t number_of_controls>
    void set_state_and_controls(const std::array<Timeseries_t,number_of_inputs>& inputs,
                                const std::array<Timeseries_t,number_of_controls>& controls);

    template<size_t number_of_inputs, size_t number_of_controls>
    void set_state_and_control_upper_lower_and_default_values(std::array<scalar,number_of_inputs>& inputs_def,
                                                               std::array<scalar,number_of_inputs>& inputs_lb,
                                                               std::array<scalar,number_of_inputs>& inputs_ub,
                                                               std::array<scalar,number_of_controls>& controls_def,
                                                               std::array<scalar,number_of_controls>& controls_lb,
                                                               std::array<scalar,number_of_controls>& controls_ub
                                                              ) const;

    template<size_t number_of_inputs, size_t number_of_controls>
    void set_state_and_control_names(std::array<std::string,number_of_inputs>& inputs,
                                     std::array<std::string,number_of_controls>& controls) const;

    static std::string type() { return "axle_car_6dof_fsae"; }

    bool is_ready() const { return base_type::is_ready() &&
        std::all_of(__used_parameters.begin(), __used_parameters.end(), [](const auto& v) -> auto { return v; }); }

    std::unordered_map<std::string,Timeseries_t> get_outputs_map() const
    {
        auto map = get_outputs_map_self();
        const auto base_type_map = base_type::get_outputs_map();
        map.insert(base_type_map.cbegin(), base_type_map.cend());
        return map;
    }

 private:
    scalar _track = 0.0;
    std::array<scalar,2> _y_tire = {0.0, 0.0};

    scalar _k_wheel = 0.0;
    scalar _k_antiroll = 0.0;
    scalar _c_damper = 0.0;

    scalar _throttle_smooth_pos = 0.0;
    scalar _I = 0.0;
    scalar _differential_stiffness = 0.0;
    scalar _regen_coefficient = 0.0;
    scalar _camber_static = 0.0;
    scalar _camber_gain_roll = 0.0;
    scalar _toe_static = 0.0;
    scalar _toe_gain_roll = 0.0;
    std::array<Timeseries_t,2> _camber = {0.0, 0.0};
    std::array<Timeseries_t,2> _toe = {0.0, 0.0};

    Timeseries_t _phi = 0.0;
    Timeseries_t _dphi = 0.0;

    std::array<Timeseries_t,2> _s = {0.0, 0.0};
    std::array<Timeseries_t,2> _ds = {0.0, 0.0};

    Timeseries_t _kappa_dimensionless_left = 0.0;
    Timeseries_t _kappa_dimensionless_right = 0.0;
    Timeseries_t _dangular_momentum_dt_left = 0.0;
    Timeseries_t _dangular_momentum_dt_right = 0.0;
    Timeseries_t _torque_left = 0.0;
    Timeseries_t _torque_right = 0.0;

    Timeseries_t _delta = 0.0;
    std::array<scalar,2> _beta = {0.0, 0.0};

    Engine<Timeseries_t> _engine;
    Brake<Timeseries_t>  _brakes;

    template<typename T = Axle_mode<0,0>>
    std::enable_if_t<std::is_same<T,POWERED_WITH_DIFFERENTIAL<0,0>>::value,std::vector<Database_parameter_mutable>>
    get_parameters() { return
    {
        { "track", _track },
        { "stiffness/wheel-rate", _k_wheel },
        { "stiffness/antiroll", _k_antiroll },
        { "stiffness/damper", _c_damper },
        { "inertia", _I },
        { "differential_stiffness", _differential_stiffness },
        { "smooth_throttle_coeff", _throttle_smooth_pos },
        { "regen_coefficient", _regen_coefficient },
        { "kinematics/camber_static", _camber_static },
        { "kinematics/camber_gain_roll", _camber_gain_roll },
        { "kinematics/toe_static", _toe_static },
        { "kinematics/toe_gain_roll", _toe_gain_roll }
    };}

    template<typename T = Axle_mode<0,0>>
    std::enable_if_t<std::is_same<T,STEERING_WITH_KAPPA<0,0>>::value,std::vector<Database_parameter_mutable>>
    get_parameters() { return
    {
        { "track", _track },
        { "stiffness/wheel-rate", _k_wheel },
        { "stiffness/antiroll", _k_antiroll },
        { "stiffness/damper", _c_damper },
        { "inertia", _I },
        { "beta-steering/left", _beta[LEFT] },
        { "beta-steering/right", _beta[RIGHT] },
        { "smooth_throttle_coeff", _throttle_smooth_pos },
        { "kinematics/camber_static", _camber_static },
        { "kinematics/camber_gain_roll", _camber_gain_roll },
        { "kinematics/toe_static", _toe_static },
        { "kinematics/toe_gain_roll", _toe_gain_roll }
    };}

    std::vector<bool> __used_parameters = std::vector<bool>(get_parameters().size(), false);

    std::unordered_map<std::string,Timeseries_t> get_outputs_map_self() const
    {
        return
        {
            {base_type::_name + ".left-tire.camber", _camber[LEFT]},
            {base_type::_name + ".right-tire.camber", _camber[RIGHT]},
            {base_type::_name + ".left-tire.toe", _toe[LEFT]},
            {base_type::_name + ".right-tire.toe", _toe[RIGHT]}
        };
    }
};

#include "axle_car_6dof_fsae.hpp"

#endif
