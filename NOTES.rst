Notes
*****

2019-11-27
----------

1. Mismatch between the AR6 variables:

   | Emissions\|CO2\|Energy\|Demand\|Transportation\|Road\|Passenger\|LDV
   | Energy Service\|Transportation\|Passenger\|Road\|LDV
   | Final Energy\|Transportation\|Passenger
   | Final Energy\|Transportation\|Road\|Passenger
   | Final Energy\|Transportation\|Road\|Passenger\|2W&3W

   LDV-specific variables are provided for *activity* and *emissions* quantities, but not for *energy*.

   This prevents calculation of the energy-intensity of LDV activity.

2. IAM coverage of “Final Energy|Transportation|Freight” is good, while “|Passenger”
   has only 1 series:

   | $ python3 main.py coverage
   | INFO    Get AR6 data for 1 variable(s)
   | INFO      done; 32938 observations.
   |
   | Coverage of {'variable': ['Final Energy|Transportation|Freight']}
   | Note: for fig_4 energy intensity
   |   AR6:
   |     14332 observations
   |     187 (model, scenario) combinations
   |   iTEM MIP2:
   |     0 observations
   |
   | INFO    Get AR6 data for 1 variable(s)
   | INFO      done; 12786 observations.
   | INFO    Get iTEM MIP2 data for 1 variable(s)
   |
   | Coverage of {'variable': ['Final Energy|Transportation|Passenger']}
   | Note: for fig_4 energy intensity
   |   AR6:
   |     24 observations
   |     1 (model, scenario) combinations
   |   iTEM MIP2:
   |     25 observations
   |     3 (model, scenario) combinations
