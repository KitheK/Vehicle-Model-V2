#include "gtest/gtest.h"
#include "src/core/vehicles/fsae6dof.h"
#include "src/core/applications/steady_state.h"
#include "src/main/c/fastestlapc.h"
#include <cmath>

using Front_left_tire_type  = fsae6dof<scalar>::Front_left_tire_type;
using Front_right_tire_type = fsae6dof<scalar>::Front_right_tire_type;
using Rear_left_tire_type   = fsae6dof<scalar>::Rear_left_tire_type;
using Rear_right_tire_type  = fsae6dof<scalar>::Rear_right_tire_type;

using Front_axle_t = fsae6dof<scalar>::Front_axle_t;
using Rear_axle_t  = fsae6dof<scalar>::Rear_axle_t;
using Chassis_t    = fsae6dof<scalar>::Chassis_t;
using Road_t       = fsae6dof<scalar>::Road_cartesian_t;

static_assert(Front_axle_t::input_names::KAPPA_LEFT  == 0);
static_assert(Front_axle_t::input_names::KAPPA_RIGHT == 1);
static_assert(Rear_axle_t::input_names::KAPPA_LEFT   == 2);
static_assert(Rear_axle_t::input_names::KAPPA_RIGHT  == 3);
static_assert(Chassis_t::input_names::velocity_x_mps == 4);
static_assert(Chassis_t::input_names::velocity_y_mps == 5);
static_assert(Chassis_t::input_names::yaw_rate_radps == 6);
static_assert(Chassis_t::input_names::Z              == 7);
static_assert(Chassis_t::input_names::PHI            == 8);
static_assert(Chassis_t::input_names::MU             == 9);
static_assert(Chassis_t::input_names::DZDT           == 10);
static_assert(Chassis_t::input_names::DPHIDT         == 11);
static_assert(Chassis_t::input_names::DMUDT          == 12);
static_assert(Chassis_t::input_names::T_FL           == 13);
static_assert(Chassis_t::input_names::T_FR           == 14);
static_assert(Chassis_t::input_names::T_RL           == 15);
static_assert(Chassis_t::input_names::T_RR           == 16);
static_assert(Road_t::input_names::X                 == 17);
static_assert(Road_t::input_names::Y                 == 18);
static_assert(Road_t::input_names::PSI               == 19);
static_assert(fsae6dof<scalar>::cartesian::number_of_inputs == 20);

static_assert(Front_axle_t::control_names::STEERING == 0);
static_assert(Chassis_t::control_names::throttle   == 1);
static_assert(Chassis_t::control_names::brake_bias == 2);
static_assert(fsae6dof<scalar>::cartesian::number_of_controls == 3);

class fsae6dof_test : public testing::Test
{
 protected:
    Xml_document database = {"./database/vehicles/fsae/ubco-2026-ev.xml", true};

    std::array<scalar, fsae6dof<scalar>::cartesian::number_of_inputs> default_q() const
    {
        std::array<scalar, fsae6dof<scalar>::cartesian::number_of_inputs> q{};
        q[Chassis_t::input_names::T_FL] = 298.15;
        q[Chassis_t::input_names::T_FR] = 298.15;
        q[Chassis_t::input_names::T_RL] = 298.15;
        q[Chassis_t::input_names::T_RR] = 298.15;
        return q;
    }
};

TEST_F(fsae6dof_test, indexes)
{
    EXPECT_EQ(Front_axle_t::input_names::KAPPA_LEFT,  0);
    EXPECT_EQ(Front_axle_t::input_names::KAPPA_RIGHT, 1);
    EXPECT_EQ(Rear_axle_t::input_names::KAPPA_LEFT,   2);
    EXPECT_EQ(Rear_axle_t::input_names::KAPPA_RIGHT,  3);
    EXPECT_EQ(Chassis_t::input_names::velocity_x_mps, 4);
    EXPECT_EQ(Chassis_t::input_names::Z,              7);
    EXPECT_EQ(Road_t::input_names::PSI,              19);
    EXPECT_EQ(fsae6dof<scalar>::cartesian::number_of_inputs, 20);
    EXPECT_EQ(Front_axle_t::control_names::STEERING, 0);
    EXPECT_EQ(Chassis_t::control_names::throttle,    1);
    EXPECT_EQ(Chassis_t::control_names::brake_bias,  2);
    EXPECT_EQ(fsae6dof<scalar>::cartesian::number_of_controls, 3);
}

TEST_F(fsae6dof_test, vehicle_from_xml_variable_names)
{
    fsae6dof<double>::cartesian car(database);
    auto [s_name, q_names, u_names] = car.get_state_and_control_names();

    EXPECT_EQ(q_names[Front_axle_t::input_names::KAPPA_LEFT],  "front-axle.left-tire.kappa");
    EXPECT_EQ(q_names[Front_axle_t::input_names::KAPPA_RIGHT], "front-axle.right-tire.kappa");
    EXPECT_EQ(q_names[Rear_axle_t::input_names::KAPPA_LEFT],   "rear-axle.left-tire.kappa");
    EXPECT_EQ(q_names[Rear_axle_t::input_names::KAPPA_RIGHT],  "rear-axle.right-tire.kappa");
    EXPECT_EQ(q_names[Chassis_t::input_names::velocity_x_mps], "chassis.velocity.x");
    EXPECT_EQ(q_names[Chassis_t::input_names::Z],              "chassis.position.z");
    EXPECT_EQ(q_names[Chassis_t::input_names::T_FL],           "chassis.tire.temperature.fl");
    EXPECT_EQ(u_names[Front_axle_t::control_names::STEERING],  "front-axle.steering-angle");
    EXPECT_EQ(u_names[Chassis_t::control_names::throttle],     "chassis.throttle");
    EXPECT_EQ(u_names[Chassis_t::control_names::brake_bias],   "chassis.brake-bias");
}

TEST_F(fsae6dof_test, is_ready)
{
    fsae6dof<double>::cartesian car(database);
    EXPECT_TRUE(car.is_ready());
}

TEST_F(fsae6dof_test, ode_straight_running_is_finite)
{
    fsae6dof<double>::cartesian car(database);

    auto q = default_q();
    q[Chassis_t::input_names::velocity_x_mps] = 20.0;
    q[Chassis_t::input_names::Z] = 0.02;

    std::array<scalar, fsae6dof<scalar>::cartesian::number_of_controls> u{};
    u[Chassis_t::control_names::brake_bias] = 0.53;

    auto [states, dqdt] = car(q, u, 0.0);

    for (size_t i = 0; i < dqdt.size(); ++i)
        EXPECT_TRUE(std::isfinite(dqdt[i])) << "dqdt[" << i << "] is not finite";

    const auto Fz = car.get_chassis().get_force().z();
    EXPECT_TRUE(std::isfinite(Fz));

    const auto Fz_fl = car.get_chassis().get_front_axle().template get_tire<0>().get_force().z();
    const auto Fz_fr = car.get_chassis().get_front_axle().template get_tire<1>().get_force().z();
    const auto Fz_rl = car.get_chassis().get_rear_axle().template get_tire<0>().get_force().z();
    const auto Fz_rr = car.get_chassis().get_rear_axle().template get_tire<1>().get_force().z();

    EXPECT_TRUE(std::isfinite(Fz_fl));
    EXPECT_TRUE(std::isfinite(Fz_fr));
    EXPECT_TRUE(std::isfinite(Fz_rl));
    EXPECT_TRUE(std::isfinite(Fz_rr));
    EXPECT_LT(Fz_fl, 0.0);
    EXPECT_LT(Fz_fr, 0.0);
    EXPECT_LT(Fz_rl, 0.0);
    EXPECT_LT(Fz_rr, 0.0);
}

TEST_F(fsae6dof_test, ev_envelope_torque_limited_at_low_speed)
{
    fsae6dof<double>::cartesian car(database);

    auto q = default_q();
    q[Chassis_t::input_names::velocity_x_mps] = 5.0;
    q[Chassis_t::input_names::Z] = 0.02;

    std::array<scalar, fsae6dof<scalar>::cartesian::number_of_controls> u{};
    u[Chassis_t::control_names::throttle] = 1.0;
    u[Chassis_t::control_names::brake_bias] = 0.53;

    (void)car(q, u, 0.0);

    const auto power = car.get_chassis().get_rear_axle().get_engine().get_power();
    EXPECT_GT(power, 0.0);
    EXPECT_LT(power, 80.0e3);
}

TEST_F(fsae6dof_test, ev_envelope_power_capped)
{
    fsae6dof<double>::cartesian car(database);

    auto q = default_q();
    q[Chassis_t::input_names::velocity_x_mps] = 40.0;
    q[Chassis_t::input_names::Z] = 0.02;

    std::array<scalar, fsae6dof<scalar>::cartesian::number_of_controls> u{};
    u[Chassis_t::control_names::throttle] = 1.0;
    u[Chassis_t::control_names::brake_bias] = 0.53;

    (void)car(q, u, 0.0);

    const auto power = car.get_chassis().get_rear_axle().get_engine().get_power();
    EXPECT_GT(power, 50.0e3);
    EXPECT_LT(power, 80.0e3 * 1.01);
}

TEST_F(fsae6dof_test, battery_energy_integral_is_motor_power)
{
    fsae6dof<double>::cartesian car(database);

    auto q = default_q();
    q[Chassis_t::input_names::velocity_x_mps] = 20.0;
    q[Chassis_t::input_names::Z] = 0.02;

    std::array<scalar, fsae6dof<scalar>::cartesian::number_of_controls> u{};
    u[Chassis_t::control_names::throttle] = 1.0;
    u[Chassis_t::control_names::brake_bias] = 0.53;

    (void)car(q, u, 0.0);

    const auto integrals = car.compute_integral_quantities();
    EXPECT_EQ(integrals.size(), 5u);
    EXPECT_NEAR(integrals[0], car.get_chassis().get_rear_axle().get_engine().get_power()*1.0e-6, 1.0e-12);
}

TEST_F(fsae6dof_test, aero_scale_unity_at_nominal_attitude)
{
    fsae6dof<double>::cartesian car(database);

    auto q = default_q();
    q[Chassis_t::input_names::velocity_x_mps] = 20.0;
    q[Chassis_t::input_names::Z] = 0.0;

    std::array<scalar, fsae6dof<scalar>::cartesian::number_of_controls> u{};
    u[Chassis_t::control_names::brake_bias] = 0.53;

    (void)car(q, u, 0.0);

    EXPECT_NEAR(car.get_chassis().get_cl_scale(), 1.0, 1.0e-12);
    EXPECT_NEAR(car.get_chassis().get_cd_scale(), 1.0, 1.0e-12);
    EXPECT_NEAR(car.get_chassis().get_front_aero_distribution(), 0.48, 0.02);
}

TEST_F(fsae6dof_test, aero_cl_increases_when_heave_decreases)
{
    fsae6dof<double>::cartesian car(database);

    auto q = default_q();
    q[Chassis_t::input_names::velocity_x_mps] = 20.0;
    q[Chassis_t::input_names::Z] = -0.01;

    std::array<scalar, fsae6dof<scalar>::cartesian::number_of_controls> u{};
    u[Chassis_t::control_names::brake_bias] = 0.53;

    (void)car(q, u, 0.0);

    EXPECT_NEAR(car.get_chassis().get_cl_scale(), 1.0 + 8.0*0.01, 1.0e-12);
    EXPECT_GT(car.get_chassis().get_cl_scale(), 1.0);
}

TEST_F(fsae6dof_test, tire_heats_when_sliding)
{
    fsae6dof<double>::cartesian car(database);

    auto q = default_q();
    q[Chassis_t::input_names::velocity_x_mps] = 20.0;
    q[Chassis_t::input_names::Z] = 0.02;
    q[Front_axle_t::input_names::KAPPA_LEFT] = 0.15;
    q[Front_axle_t::input_names::KAPPA_RIGHT] = 0.15;
    q[Rear_axle_t::input_names::KAPPA_LEFT] = 0.15;
    q[Rear_axle_t::input_names::KAPPA_RIGHT] = 0.15;

    std::array<scalar, fsae6dof<scalar>::cartesian::number_of_controls> u{};
    u[Chassis_t::control_names::brake_bias] = 0.53;

    auto [states, dqdt] = car(q, u, 0.0);
    EXPECT_GT(dqdt[Chassis_t::state_names::T_FL], 0.0);
    EXPECT_GT(dqdt[Chassis_t::state_names::T_RL], 0.0);
}

TEST_F(fsae6dof_test, grip_scale_peaks_near_optimal_temperature)
{
    fsae6dof<double>::cartesian car(database);
    const auto at_opt = car.get_chassis().grip_scale_from_temperature(353.15);
    const auto at_amb = car.get_chassis().grip_scale_from_temperature(298.15);
    EXPECT_NEAR(at_opt, 1.0, 1.0e-12);
    EXPECT_LT(at_amb, at_opt);
}

TEST_F(fsae6dof_test, camber_follows_roll_gain)
{
    fsae6dof<double>::cartesian car(database);

    auto q = default_q();
    q[Chassis_t::input_names::velocity_x_mps] = 20.0;
    q[Chassis_t::input_names::Z] = 0.02;
    q[Chassis_t::input_names::PHI] = 0.05;

    std::array<scalar, fsae6dof<scalar>::cartesian::number_of_controls> u{};
    u[Chassis_t::control_names::brake_bias] = 0.53;

    (void)car(q, u, 0.0);

    EXPECT_NEAR(car.get_chassis().get_front_axle().get_camber_left(), -0.01745 + 0.3*0.05, 1.0e-6);
    EXPECT_NEAR(car.get_chassis().get_front_axle().get_camber_right(), -0.01745 - 0.3*0.05, 1.0e-6);
    EXPECT_NEAR(car.get_chassis().get_heave(), 0.02, 1.0e-12);
    EXPECT_NEAR(car.get_chassis().get_roll(), 0.05, 1.0e-12);
}

TEST_F(fsae6dof_test, load_transfer_positive_roll_loads_right_tires)
{
    fsae6dof<double>::cartesian car(database);

    auto q = default_q();
    q[Chassis_t::input_names::velocity_x_mps] = 20.0;
    q[Chassis_t::input_names::Z] = 0.02;
    q[Chassis_t::input_names::PHI] = 0.05;

    std::array<scalar, fsae6dof<scalar>::cartesian::number_of_controls> u{};
    u[Chassis_t::control_names::brake_bias] = 0.53;

    (void)car(q, u, 0.0);

    const auto Fz_fl = car.get_chassis().get_front_axle().template get_tire<0>().get_force().z();
    const auto Fz_fr = car.get_chassis().get_front_axle().template get_tire<1>().get_force().z();
    const auto Fz_rl = car.get_chassis().get_rear_axle().template get_tire<0>().get_force().z();
    const auto Fz_rr = car.get_chassis().get_rear_axle().template get_tire<1>().get_force().z();

    EXPECT_LT(Fz_fl, 0.0);
    EXPECT_LT(Fz_fr, 0.0);
    EXPECT_LT(Fz_rl, 0.0);
    EXPECT_LT(Fz_rr, 0.0);
    EXPECT_LT(Fz_fr, Fz_fl);
    EXPECT_LT(Fz_rr, Fz_rl);
}

TEST_F(fsae6dof_test, regen_motor_power_is_negative)
{
    fsae6dof<double>::cartesian car(database);

    auto q = default_q();
    q[Chassis_t::input_names::velocity_x_mps] = 20.0;
    q[Chassis_t::input_names::Z] = 0.02;

    std::array<scalar, fsae6dof<scalar>::cartesian::number_of_controls> u{};
    u[Chassis_t::control_names::throttle] = -1.0;
    u[Chassis_t::control_names::brake_bias] = 0.53;

    (void)car(q, u, 0.0);

    const auto power = car.get_chassis().get_rear_axle().get_engine().get_power();
    EXPECT_LT(power, 0.0);

    const auto integrals = car.compute_integral_quantities();
    EXPECT_NEAR(integrals[0], power * 1.0e-6, 1.0e-12);
}

TEST_F(fsae6dof_test, steady_state_zero_g_solves)
{
    Xml_document database_ad = {"./database/vehicles/fsae/ubco-2026-ev.xml", true};
    fsae6dof<CppAD::AD<scalar>>::cartesian car(database_ad);
    Steady_state ss(car);

    const auto sol = ss.solve(15.0, 0.0, 0.0, 1, false, {}, false);
    EXPECT_TRUE(sol.solved);
    EXPECT_TRUE(std::isfinite(sol.inputs[Chassis_t::input_names::Z]));
    EXPECT_NEAR(sol.ax, 0.0, 1.0e-12);
    EXPECT_NEAR(sol.ay, 0.0, 1.0e-12);
}

TEST_F(fsae6dof_test, load_transfer_at_lateral_acceleration)
{
    Xml_document database_ad = {"./database/vehicles/fsae/ubco-2026-ev.xml", true};
    fsae6dof<CppAD::AD<scalar>>::cartesian car_ad(database_ad);
    Steady_state ss(car_ad);

    const scalar v = 15.0;
    const scalar ay = 2.0;
    auto sol_0g = ss.solve(v, 0.0, 0.0, 1, false, {}, false);
    ASSERT_TRUE(sol_0g.solved);

    const auto x0 = car_ad.get_x(sol_0g.inputs, sol_0g.controls, v);
    const auto sol = ss.solve(v, 0.0, ay, 1, true, x0, false);
    ASSERT_TRUE(sol.solved);
    EXPECT_NEAR(sol.ay, ay, 1.0e-12);

    fsae6dof<double>::cartesian car(database);
    (void)car(sol.inputs, sol.controls, 0.0);

    const auto Fz_fl = car.get_chassis().get_front_axle().template get_tire<0>().get_force().z();
    const auto Fz_fr = car.get_chassis().get_front_axle().template get_tire<1>().get_force().z();
    const auto Fz_rl = car.get_chassis().get_rear_axle().template get_tire<0>().get_force().z();
    const auto Fz_rr = car.get_chassis().get_rear_axle().template get_tire<1>().get_force().z();

    // SAE: +y is right, so +ay transfers load to the left. Fz is negative (compression).
    EXPECT_LT(Fz_fl, Fz_fr);
    EXPECT_LT(Fz_rl, Fz_rr);
    EXPECT_LT(car.get_chassis().get_roll(), 0.0);

    const scalar extra_left_load = (Fz_fr + Fz_rr) - (Fz_fl + Fz_rl);
    const scalar algebraic = 277.2 * ay * 0.25 / 1.2225;
    EXPECT_GT(extra_left_load, 0.0);
    EXPECT_GT(algebraic, 0.0);
}

TEST_F(fsae6dof_test, gg_diagram_smoke)
{
    Xml_document database_ad = {"./database/vehicles/fsae/ubco-2026-ev.xml", true};
    fsae6dof<CppAD::AD<scalar>>::cartesian car(database_ad);
    Steady_state ss(car);

    const scalar v = 15.0;
    auto sol_0g = ss.solve(v, 0.0, 0.0, 1, false, {}, false);
    ASSERT_TRUE(sol_0g.solved);

    constexpr size_t n = 2;
    auto [sol_max, sol_min] = ss.gg_diagram(v, n);
    ASSERT_EQ(sol_max.size(), n);
    ASSERT_EQ(sol_min.size(), n);

    for (size_t i = 0; i < n; ++i)
    {
        EXPECT_TRUE(sol_max[i].solved) << "max point " << i;
        EXPECT_TRUE(sol_min[i].solved) << "min point " << i;
        EXPECT_TRUE(std::isfinite(sol_max[i].ax));
        EXPECT_TRUE(std::isfinite(sol_max[i].ay));
        EXPECT_TRUE(std::isfinite(sol_min[i].ax));
        EXPECT_TRUE(std::isfinite(sol_min[i].ay));
    }
}

TEST_F(fsae6dof_test, create_vehicle_from_xml_c_api)
{
#ifdef TEST_LIBFASTESTLAPC
    create_vehicle_from_xml("ubco", "./database/vehicles/fsae/ubco-2026-ev.xml");

    int n_inputs = 0, n_control = 0, n_outputs = 0;
    vehicle_type_get_sizes(&n_inputs, &n_control, &n_outputs, "fsae-6dof");
    EXPECT_EQ(n_inputs, 20);
    EXPECT_EQ(n_control, 3);
    EXPECT_GT(n_outputs, 0);

    char type[32] = {};
    variable_type(type, 32, "ubco");
    EXPECT_STREQ(type, "fsae-6dof");

    delete_variable("ubco");
#else
    GTEST_SKIP();
#endif
}
