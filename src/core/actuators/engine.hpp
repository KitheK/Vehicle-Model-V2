#ifndef __ENGINE_HPP__
#define __ENGINE_HPP__

#include "lion/math/matrix_extensions.h"

template<typename Timeseries_t>
inline Engine<Timeseries_t>::Engine(Xml_document& database, const std::string& path, const bool only_max_power)
: _path(path),
  _gear_ratio(1.0),
  _only_max_power(only_max_power),
  _ev_envelope(false),
  _peak_torque(0.0),
  _maximum_power(0.0) 
{
    if ( database.has_element(path+"peak-torque") )
    {
        _ev_envelope = true;
        read_parameters(database, path, get_parameters(), __used_parameters);
        _peak_torque = database.get_element(path+"peak-torque").get_value(double());
        database.get_element(path+"peak-torque").set_attribute("__unused__","false");
        _gear_ratio = database.get_element(path+"gear-ratio").get_value(double());
        database.get_element(path+"gear-ratio").set_attribute("__unused__","false");
    }
    else if ( _only_max_power )
    {
        read_parameters(database, path, get_parameters(), __used_parameters);
    }
    else
    {
        _gear_ratio = database.get_element(path+"gear-ratio").get_value(double());
        database.get_element(path+"gear-ratio").set_attribute("__unused__","false");

        std::vector<scalar> speed = database.get_element(path+"rpm-data").get_value(std::vector<double>())*RPM;
        database.get_element(path+"rpm-data").set_attribute("__unused__","false");

        std::vector<scalar> p = database.get_element(path+"power-data").get_value(std::vector<double>())*CV;
        database.get_element(path+"power-data").set_attribute("__unused__","false");

        _p = sPolynomial(speed,p,speed.size()-1,true);
    } 

    _direct_torque = false;
}


template<typename Timeseries_t>
inline Timeseries_t Engine<Timeseries_t>::operator()(const Timeseries_t throttle_percentage, const Timeseries_t angular_speed)
{
    if ( _direct_torque )
        return throttle_percentage;

    else if ( _ev_envelope )
    {
        const Timeseries_t omega_motor = _gear_ratio * angular_speed;
        const Timeseries_t torque_power_limited = (_maximum_power*1.0e3)/(omega_motor + 1.0e-6);
        const Timeseries_t torque_motor = throttle_percentage * min(Timeseries_t(_peak_torque), torque_power_limited);
        _power = torque_motor * omega_motor;
        return torque_motor * _gear_ratio;
    }
    else if ( _only_max_power )
    {
        _power = throttle_percentage*(_maximum_power*1.0e3);
        return _power/angular_speed;
    }
    else
    {
        const double ang_speed_dbl = gear_ratio()*Value(angular_speed);
        const double speed_for_zero = 15000.0/14000.0;
        // If out of bounds, just extend the power at the bound
        if ( ang_speed_dbl < _p.get_left_bound() ) 
            return throttle_percentage*std::max(0.0,ang_speed_dbl*_p[_p.get_left_bound()]/_p.get_left_bound())/angular_speed;
    
        else if ( ang_speed_dbl > _p.get_right_bound() ) 
            return throttle_percentage*std::max(0.0,_p[_p.get_right_bound()]*(speed_for_zero - ang_speed_dbl/_p.get_right_bound())/(speed_for_zero - 1.0))/angular_speed;
    
        else
            return throttle_percentage*_p[ang_speed_dbl]/angular_speed;
    } 
}

#endif
