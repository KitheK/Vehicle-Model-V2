#ifndef FSAE6DOF_H
#define FSAE6DOF_H

#include "src/core/tire/tire_pacejka.h"
#include "src/core/chassis/axle_car_6dof_fsae.h"
#include "src/core/chassis/chassis_car_6dof_fsae.h"
#include "src/core/vehicles/track_by_polynomial.h"
#include "src/core/vehicles/track_by_arcs.h"
#include "src/core/vehicles/road_cartesian.h"
#include "src/core/vehicles/road_curvilinear.h"
#include "src/core/vehicles/dynamic_model_car.h"
#include "src/core/foundation/fastest_lap_exception.h"
#include "lion/thirdparty/include/cppad/cppad.hpp"
#include <algorithm>

template<typename Timeseries_t>
class fsae6dof
{
 public:
    fsae6dof() = delete;

    using Front_left_tire_type  = Tire_pacejka_std<Timeseries_t,0,0>;
    using Front_right_tire_type = Tire_pacejka_std<Timeseries_t,Front_left_tire_type::input_names::end,Front_left_tire_type::control_names::end>;
    using Rear_left_tire_type   = Tire_pacejka_std<Timeseries_t,Front_right_tire_type::input_names::end,Front_right_tire_type::control_names::end>;
    using Rear_right_tire_type  = Tire_pacejka_std<Timeseries_t,Rear_left_tire_type::input_names::end,Rear_left_tire_type::control_names::end>;

    using Front_axle_t = Axle_car_6dof_fsae<Timeseries_t,Front_left_tire_type,Front_right_tire_type,STEERING_WITH_KAPPA,Rear_right_tire_type::input_names::end,Rear_right_tire_type::control_names::end>;
    using Rear_axle_t  = Axle_car_6dof_fsae<Timeseries_t,Rear_left_tire_type,Rear_right_tire_type,POWERED_WITH_DIFFERENTIAL,Front_axle_t::Axle_type::input_names::end,Front_axle_t::Axle_type::control_names::end>;
    using Chassis_t    = Chassis_car_6dof_fsae<Timeseries_t,Front_axle_t,Rear_axle_t,Rear_axle_t::Axle_type::input_names::end,Rear_axle_t::Axle_type::control_names::end>;

    using Road_cartesian_t = Road_cartesian<Timeseries_t,Chassis_t::input_names::end,Chassis_t::control_names::end>;

    template<typename Track_t>
    using Road_curvilinear_t = Road_curvilinear<Timeseries_t,Track_t,Chassis_t::input_names::end,Chassis_t::control_names::end>;

 private:
    template<typename Road_type>
    class Dynamic_model : public Dynamic_model_car<Timeseries_t,Chassis_t,Road_type>
    {
     public:
        using Road_t          = Road_type;
        using Dynamic_model_t = Dynamic_model_car<Timeseries_t,Chassis_t, Road_type>;

        Dynamic_model() {}
        Dynamic_model(Xml_document& database, const Road_t& road = Road_t()) : Dynamic_model_t(database,road)
        {
            if constexpr (road_is_curvilinear<Road_t>::value)
            {
                if (road.get_track().has_elevation())
                    throw fastest_lap_exception("[ERROR] Tracks with elevation are not supported for fsae6dof vehicles.");
            }
        }

        template<typename U = Road_t>
        std::enable_if_t<road_is_curvilinear<U>::value, void> change_track(const typename U::Track_type& new_track)
        {
            Dynamic_model_t::change_track(new_track);
            if (Dynamic_model_t::get_road().get_track().has_elevation())
                throw fastest_lap_exception("[ERROR] Tracks with elevation are not supported for fsae6dof vehicles.");
        }

        static constexpr const size_t number_of_steady_state_variables = 10;
        static constexpr const size_t number_of_steady_state_equations = 14;

        static constexpr const size_t N_OL_EXTRA_CONSTRAINTS = 4;

        static constexpr const scalar acceleration_units = 1.0;

        static std::vector<scalar> steady_state_initial_guess()
        {
            return {0.0, 0.0, 0.0, 0.0, 0.02, 0.0, 0.0, 0.0, 0.0, 0.0};
        }

        static std::pair<std::vector<scalar>,std::vector<scalar>> steady_state_variable_bounds()
        {
            return { { -1.0, -1.0, -1.0, -1.0, 1.0e-4, -10.0*DEG, -10.0*DEG, -10.0*DEG, -10.0*DEG, -1.0 },
                     {  1.0,  1.0,  1.0,  1.0, 0.08  ,  10.0*DEG,  10.0*DEG,  10.0*DEG,  10.0*DEG,  1.0 } };
        }

        static std::pair<std::vector<scalar>,std::vector<scalar>> steady_state_variable_bounds_accelerate()
        {
            return steady_state_variable_bounds();
        }

        static std::pair<std::vector<scalar>,std::vector<scalar>> steady_state_variable_bounds_brake()
        {
            return steady_state_variable_bounds();
        }

        template<typename T>
        static std::vector<T> get_x(const std::array<T,Dynamic_model_t::number_of_inputs>& q,
                                         const std::array<T,Dynamic_model_t::number_of_controls>& u,
                                         scalar)
        {
            return { q[Dynamic_model_t::Chassis_type::front_axle_type::input_names::KAPPA_LEFT],
                     q[Dynamic_model_t::Chassis_type::front_axle_type::input_names::KAPPA_RIGHT],
                     q[Dynamic_model_t::Chassis_type::rear_axle_type::input_names::KAPPA_LEFT],
                     q[Dynamic_model_t::Chassis_type::rear_axle_type::input_names::KAPPA_RIGHT],
                     q[Dynamic_model_t::Chassis_type::input_names::Z],
                     q[Dynamic_model_t::Chassis_type::input_names::PHI],
                     q[Dynamic_model_t::Chassis_type::input_names::MU],
                     q[Dynamic_model_t::Road_type::input_names::PSI],
                     u[Dynamic_model_t::Chassis_type::front_axle_type::control_names::STEERING],
                     u[Dynamic_model_t::Chassis_type::control_names::throttle]
                    };
        }

        static std::pair<std::vector<scalar>,std::vector<scalar>> steady_state_constraint_bounds()
        {
            return { {0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -0.15, -0.15, -0.15, -0.15},
                     {0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,  0.15,  0.15,  0.15,  0.15} };
        }

        std::tuple<std::array<Timeseries_t,number_of_steady_state_equations>,
                   std::array<Timeseries_t,Dynamic_model_t::number_of_inputs>,
                   std::array<Timeseries_t,Dynamic_model_t::number_of_controls>>
            steady_state_equations(const std::array<Timeseries_t,number_of_steady_state_variables>& x,
                                   const Timeseries_t& ax,
                                   const Timeseries_t& ay,
                                   const Timeseries_t& v)
        {
            const Timeseries_t& psi = x[7];
            const Timeseries_t omega = ay/v;

            std::array<Timeseries_t,Dynamic_model_t::number_of_inputs> q{};
            q[Dynamic_model_t::Chassis_type::front_axle_type::input_names::KAPPA_LEFT]  = x[0];
            q[Dynamic_model_t::Chassis_type::front_axle_type::input_names::KAPPA_RIGHT] = x[1];
            q[Dynamic_model_t::Chassis_type::rear_axle_type::input_names::KAPPA_LEFT]   = x[2];
            q[Dynamic_model_t::Chassis_type::rear_axle_type::input_names::KAPPA_RIGHT]  = x[3];
            q[Dynamic_model_t::Chassis_type::input_names::velocity_x_mps] = v*cos(psi);
            q[Dynamic_model_t::Chassis_type::input_names::velocity_y_mps] = -v*sin(psi);
            q[Dynamic_model_t::Chassis_type::input_names::yaw_rate_radps] = omega;
            q[Dynamic_model_t::Chassis_type::input_names::Z] = x[4];
            q[Dynamic_model_t::Chassis_type::input_names::PHI] = x[5];
            q[Dynamic_model_t::Chassis_type::input_names::MU] = x[6];
            q[Dynamic_model_t::Chassis_type::input_names::DZDT] = 0.0;
            q[Dynamic_model_t::Chassis_type::input_names::DPHIDT] = 0.0;
            q[Dynamic_model_t::Chassis_type::input_names::DMUDT] = 0.0;
            const auto T_amb = this->get_chassis().get_t_ambient();
            q[Dynamic_model_t::Chassis_type::input_names::T_FL] = T_amb;
            q[Dynamic_model_t::Chassis_type::input_names::T_FR] = T_amb;
            q[Dynamic_model_t::Chassis_type::input_names::T_RL] = T_amb;
            q[Dynamic_model_t::Chassis_type::input_names::T_RR] = T_amb;
            q[Dynamic_model_t::Road_type::input_names::X] = 0.0;
            q[Dynamic_model_t::Road_type::input_names::Y] = 0.0;
            q[Dynamic_model_t::Road_type::input_names::PSI] = psi;

            std::array<scalar,Dynamic_model_t::number_of_controls> u_def = this->get_state_and_control_upper_lower_and_default_values().controls_def;
            std::array<Timeseries_t,Dynamic_model_t::number_of_controls> u;
            std::copy(u_def.cbegin(), u_def.cend(), u.begin());
            u[Dynamic_model_t::Chassis_type::front_axle_type::control_names::STEERING] = x[8];
            u[Dynamic_model_t::Chassis_type::control_names::throttle] = x[9];

            auto [states,dqdt] = (*this)(q,u,0.0);

            std::array<Timeseries_t,number_of_steady_state_equations> constraints;
            constraints[0] = dqdt[Dynamic_model_t::Chassis_type::state_names::DZDT];
            constraints[1] = dqdt[Dynamic_model_t::Chassis_type::state_names::yaw_rate_radps];
            constraints[2] = dqdt[Dynamic_model_t::Chassis_type::state_names::DPHIDT];
            constraints[3] = dqdt[Dynamic_model_t::Chassis_type::state_names::DMUDT];
            constraints[4] = dqdt[Dynamic_model_t::Chassis_type::state_names::com_velocity_x_mps]*sin(psi)
                            + dqdt[Dynamic_model_t::Chassis_type::state_names::com_velocity_y_mps]*cos(psi);
            constraints[5] = ax - dqdt[Dynamic_model_t::Chassis_type::state_names::com_velocity_x_mps]*cos(psi)
                                 + dqdt[Dynamic_model_t::Chassis_type::state_names::com_velocity_y_mps]*sin(psi);
            constraints[6] = this->get_chassis().get_front_axle().get_dangular_momentum_dt_left();
            constraints[7] = this->get_chassis().get_front_axle().get_dangular_momentum_dt_right();
            constraints[8] = this->get_chassis().get_rear_axle().get_dangular_momentum_dt_left();
            constraints[9] = this->get_chassis().get_rear_axle().get_dangular_momentum_dt_right();
            constraints[10] = this->get_chassis().get_front_axle().template get_tire<0>().get_lambda();
            constraints[11] = this->get_chassis().get_front_axle().template get_tire<1>().get_lambda();
            constraints[12] = this->get_chassis().get_rear_axle().template get_tire<0>().get_lambda();
            constraints[13] = this->get_chassis().get_rear_axle().template get_tire<1>().get_lambda();

            return {constraints,q,u};
        }

        std::tuple<std::vector<scalar>,std::vector<scalar>> optimal_laptime_derivative_control_bounds() const
        {
            return {{-20.0*DEG,-10.0,-10.0},{20.0*DEG,10.0,10.0}};
        }

        std::pair<std::vector<scalar>,std::vector<scalar>> optimal_laptime_extra_constraints_bounds(const scalar s) const
        {
            (void)s;
            return {{-0.15,-0.15,-0.15,-0.15},{0.15,0.15,0.15,0.15}};
        }

        std::array<Timeseries_t,N_OL_EXTRA_CONSTRAINTS> optimal_laptime_extra_constraints() const
        {
            return
            {
                this->get_chassis().get_front_axle().template get_tire<0>().get_lambda(),
                this->get_chassis().get_front_axle().template get_tire<1>().get_lambda(),
                this->get_chassis().get_rear_axle().template get_tire<0>().get_lambda(),
                this->get_chassis().get_rear_axle().template get_tire<1>().get_lambda()
            };
        }

        struct Integral_quantities
        {
            enum { IBATTERY_ENERGY, IFRONT_LEFT_TIRE_ENERGY, IFRONT_RIGHT_TIRE_ENERGY,
                                  IREAR_LEFT_TIRE_ENERGY, IREAR_RIGHT_TIRE_ENERGY, N_INTEGRAL_QUANTITIES };
            inline const static std::vector<std::string> names = {"battery-energy","tire-fl-energy","tire-fr-energy","tire-rl-energy","tire-rr-energy"};
        };

        std::array<Timeseries_t,Integral_quantities::N_INTEGRAL_QUANTITIES> compute_integral_quantities() const
        {
            std::array<Timeseries_t,Integral_quantities::N_INTEGRAL_QUANTITIES> outputs;
            outputs[Integral_quantities::IBATTERY_ENERGY]           = this->get_chassis().get_rear_axle().get_engine().get_power()*1.0e-6;
            outputs[Integral_quantities::IFRONT_LEFT_TIRE_ENERGY]   = -this->get_chassis().get_front_axle().template get_tire<0>().get_dissipation()*1.0e-6;
            outputs[Integral_quantities::IFRONT_RIGHT_TIRE_ENERGY]  = -this->get_chassis().get_front_axle().template get_tire<1>().get_dissipation()*1.0e-6;
            outputs[Integral_quantities::IREAR_LEFT_TIRE_ENERGY]    = -this->get_chassis().get_rear_axle().template get_tire<0>().get_dissipation()*1.0e-6;
            outputs[Integral_quantities::IREAR_RIGHT_TIRE_ENERGY]   = -this->get_chassis().get_rear_axle().template get_tire<1>().get_dissipation()*1.0e-6;
            return outputs;
        }
    };

 public:
    using cartesian = Dynamic_model<Road_cartesian_t>;

    template<typename Track_t>
    using curvilinear = Dynamic_model<Road_curvilinear_t<Track_t>>;

    using curvilinear_p = curvilinear<Track_by_polynomial>;
    using curvilinear_a = curvilinear<Track_by_arcs>;
};

struct fsae6dof_all
{
    fsae6dof_all(Xml_document& database_xml)
    : cartesian_scalar(database_xml),
      curvilinear_scalar(database_xml),
      cartesian_ad(database_xml),
      curvilinear_ad(database_xml)
    {}

    using vehicle_scalar_curvilinear = fsae6dof<scalar>::curvilinear_p;
    using vehicle_ad_curvilinear = fsae6dof<CppAD::AD<scalar>>::curvilinear_p;

    fsae6dof<CppAD::AD<scalar>>::curvilinear_p& get_curvilinear_ad_car() { return curvilinear_ad; }
    fsae6dof<scalar>::curvilinear_p& get_curvilinear_scalar_car() { return curvilinear_scalar; }

    template<typename T>
    void set_parameter(const std::string& parameter, const T value)
    {
        cartesian_scalar.set_parameter(parameter, value);
        curvilinear_scalar.set_parameter(parameter, value);
        cartesian_ad.set_parameter(parameter, value);
        curvilinear_ad.set_parameter(parameter, value);
    }

    template<typename ... Args>
    void add_parameter(const std::string& parameter_name, Args&& ... args)
    {
        cartesian_scalar.add_parameter(parameter_name, std::forward<Args>(args)...);
        curvilinear_scalar.add_parameter(parameter_name, std::forward<Args>(args)...);
        cartesian_ad.add_parameter(parameter_name, std::forward<Args>(args)...);
        curvilinear_ad.add_parameter(parameter_name, std::forward<Args>(args)...);
    }

    fsae6dof<scalar>::cartesian                 cartesian_scalar;
    fsae6dof<scalar>::curvilinear_p             curvilinear_scalar;
    fsae6dof<CppAD::AD<scalar>>::cartesian      cartesian_ad;
    fsae6dof<CppAD::AD<scalar>>::curvilinear_p  curvilinear_ad;
};

#endif
