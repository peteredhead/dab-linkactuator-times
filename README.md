# dab-linkactuator-times
Quick tool to parse an ETI file and display the timings of link actuator changes.

## Usage
```
cat <eti_file> | python la_times.py
```

## Example Output
```
Frame	ETI time	Broadcast time	Event Details
25	0:00:00.600000	unknown	First occurance of linkset 197H (Inactive)
25	0:00:00.600000	unknown	First occurance of linkset 1B0H (Active)
25	0:00:00.600000	unknown	First occurance of linkset 197S (Active)
2265	0:00:54.360000	2014-09-18 16:30:17.088000	Updated members of link set 197H: DAB - C36B, C66B, C366, C361, C460, C36E, C560, C661, C363, C364, C362, C368 
2267	0:00:54.408000	2014-09-18 16:30:17.136000	Updated members of link set 1B0H: DAB - C361, C661 
26548	0:10:37.152000	2014-09-18 16:40:00.312000	Setting linkset 1B0H to Inactive
38370	0:15:20.880000	2014-09-18 16:44:43.536000	Setting linkset 1B0H to Active

```
