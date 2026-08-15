#include "gtest/gtest.h"
#include "src/core/actuators/engine.h"
#include <iomanip>
#include <fstream>


class Engine_curve : public ::testing::Test
{
 protected:
    Engine_curve()
    {
        database.create_root_element("vehicle");

        database.add_element("vehicle/rear-axle/engine/rpm-data").set_value("10049.296 10225.352 10478.873 10774.648 10943.662 11169.014 11535.211 11929.577 "
                "12197.183 12464.789 12690.141 12971.831 13183.099 13366.197 13507.042 13647.887 "
                "13746.479 13816.901 13859.155 13901.408 14007.042");
        database.add_element("vehicle/rear-axle/engine/power-data").set_value("14.828 17.724 22.138 26.552 29.31  32.897 35.931 "
                "38.414 40.207 42.138 44.483 46.276 44.897 42 "
                "39.655 36.207 33.31  30.276 27.103 24.207 20.345");
        database.add_element("vehicle/rear-axle/engine/gear-ratio").set_value("8.15");
        _engine = Engine<scalar>(database, "vehicle/rear-axle/engine/",false);
    }

    Xml_document database ;
    Engine<scalar> _engine;
};


TEST_F(Engine_curve,evaluation_at_control_points)
{
    const std::vector<scalar> speed = 
        database.get_element("vehicle/rear-axle/engine/rpm-data").get_value(std::vector<double>())*RPM;
    const std::vector<scalar> power =
        database.get_element("vehicle/rear-axle/engine/power-data").get_value(std::vector<double>())*CV;

    EXPECT_EQ(speed.size(), power.size());

    for (size_t i = 0; i < speed.size(); ++i)
    {
        const scalar axle_speed = speed[i]/_engine.gear_ratio();
        const scalar power_computed = _engine(1.0,axle_speed)*axle_speed;
        EXPECT_NEAR( std::abs(power[i]-power_computed)/power[i], 0.0, 2.0e-2) << "with i = " << i ;
    }

}

class Engine_ev_envelope : public ::testing::Test
{
 protected:
    Engine_ev_envelope()
    {
        database.create_root_element("vehicle");
        database.add_element("vehicle/rear-axle/engine/maximum-power").set_value("80.0");
        database.add_element("vehicle/rear-axle/engine/peak-torque").set_value("240.0");
        database.add_element("vehicle/rear-axle/engine/gear-ratio").set_value("4.8");
        _engine = Engine<scalar>(database, "vehicle/rear-axle/engine/", true);
    }

    Xml_document database;
    Engine<scalar> _engine;
};

TEST_F(Engine_ev_envelope, torque_limited_at_low_speed)
{
    const scalar omega_wheel = 20.0;
    const scalar torque_wheel = _engine(1.0, omega_wheel);
    EXPECT_NEAR(torque_wheel, 240.0 * 4.8, 1.0e-6);
    EXPECT_NEAR(_engine.get_power(), 240.0 * 4.8 * omega_wheel, 1.0e-4);
}

TEST_F(Engine_ev_envelope, power_limited_at_high_speed)
{
    const scalar omega_wheel = 200.0;
    const scalar omega_motor = 4.8 * omega_wheel;
    const scalar torque_wheel = _engine(1.0, omega_wheel);
    const scalar expected_motor_torque = 80000.0 / omega_motor;
    EXPECT_NEAR(torque_wheel, expected_motor_torque * 4.8, 1.0e-4);
    EXPECT_NEAR(_engine.get_power(), 80000.0, 1.0e-3);
}

TEST_F(Engine_ev_envelope, regen_is_negative_torque)
{
    const scalar omega_wheel = 20.0;
    const scalar torque_wheel = _engine(-0.3, omega_wheel);
    EXPECT_NEAR(torque_wheel, -0.3 * 240.0 * 4.8, 1.0e-6);
    EXPECT_LT(_engine.get_power(), 0.0);
}
