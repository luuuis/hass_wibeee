[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)

# Home Assistant: Wibeee Component
![wibeee_logo](https://wibeee.com/wp-content/uploads/2018/09/logo.png)

This is a Home Assistant Custom Component originally developed to integrate CIRCUTOR Wibeee (3 phase)
and Mirubee energy monitors. It has been found to work on on similar devices that are listed below:

| Device        | Model           | Link  |
| ------------- |:-------------:| -----:|
|Circuitor Wibeee| 3 phases | http://wibeee.circutor.com/index_en.html |
|Circuitor Wibeee| 1 phase |  http://wibeee.circutor.com/index_en.html  |
|Mirubee| Unknown models |  https://mirubee.com/es/3-productos |

# How it works

Once the devices are installed and connected to local wireless network, current energy consumption
values are exposed in XML format at the following resource:

`http://<wibeee_ip>/en/status.xml`

Example XML are listed in [examples](./examples).

## Installation

Use [HACS](https://hacs.xyz) (preferred) or follow the manual instructions below.

### HACS
Custom repository installation: 
1. Open HACS
2. Go to Integrations
3. In the top right corner, click on the 3 dots and select `Custom repositories`
4. Add this repo URL `https://github.com/luuuis/hass_wibeee` and select `Integration` as the category.
5. Install and follow the Home Assistant Configuration instructions below.

### Manual installation

1. Download `hass_wibeee.zip` from https://github.com/luuuis/hass_wibeee/releases/latest
2. Unzip into `<hass_folder>/custom_components`
```
unzip hass_wibeee.zip -d <hass_folder>/custom_components/wibeee
```

# Configuration
1. Add device to home assistant configuration file configuration.yaml

```
sensor:
- platform: wibeee
  host: 192.168.xx.xx
```

2. (optional) Add new created sensors to groups.yaml

```
supplies_view:
  view: yes
  name: Supplies
  #icon: mdi:network
  entities:
    - group.wibeee_phase1
    - group.wibeee_phase2
    - group.wibeee_phase3
    - group.wibeee_phase4
....

....
wibeee_phase1:
  name: 'Wibeee Phase 1'
  entities:
    - sensor.wibeee_phase1_active_energy
    - sensor.wibeee_phase1_active_power
    - sensor.wibeee_phase1_apparent_power
    - sensor.wibeee_phase1_capacitive_reactive_energy
    - sensor.wibeee_phase1_capacitive_reactive_power
    - sensor.wibeee_phase1_frequency
    - sensor.wibeee_phase1_inductive_reactive_energy
    - sensor.wibeee_phase1_inductive_reactive_power
    - sensor.wibeee_phase1_irms
    - sensor.wibeee_phase1_power_factor
    - sensor.wibeee_phase1_vrms
wibeee_phase2:
  name: 'Wibeee Phase 2'
  entities:
    - sensor.wibeee_phase2_active_energy
    - sensor.wibeee_phase2_active_power
    - sensor.wibeee_phase2_apparent_power
    - sensor.wibeee_phase2_capacitive_reactive_energy
    - sensor.wibeee_phase2_capacitive_reactive_power
    - sensor.wibeee_phase2_frequency
    - sensor.wibeee_phase2_inductive_reactive_energy
    - sensor.wibeee_phase2_inductive_reactive_power
    - sensor.wibeee_phase2_irms
    - sensor.wibeee_phase2_power_factor
    - sensor.wibeee_phase2_vrms
wibeee_phase3:
  name: 'Wibeee Phase 3'
  entities:
    - sensor.wibeee_phase3_active_energy
    - sensor.wibeee_phase3_active_power
    - sensor.wibeee_phase3_apparent_power
    - sensor.wibeee_phase3_capacitive_reactive_energy
    - sensor.wibeee_phase3_capacitive_reactive_power
    - sensor.wibeee_phase3_frequency
    - sensor.wibeee_phase3_inductive_reactive_energy
    - sensor.wibeee_phase3_inductive_reactive_power
    - sensor.wibeee_phase3_irms
    - sensor.wibeee_phase3_power_factor
    - sensor.wibeee_phase3_vrms
wibeee_phase4:
  name: 'Wibeee Phase 4 = Total'
  entities:
    - sensor.wibeee_phase4_active_energy
    - sensor.wibeee_phase4_active_power
    - sensor.wibeee_phase4_apparent_power
    - sensor.wibeee_phase4_capacitive_reactive_energy
    - sensor.wibeee_phase4_capacitive_reactive_power
    - sensor.wibeee_phase4_frequency
    - sensor.wibeee_phase4_inductive_reactive_energy
    - sensor.wibeee_phase4_inductive_reactive_power
    - sensor.wibeee_phase4_irms
    - sensor.wibeee_phase4_power_factor
    - sensor.wibeee_phase4_vrms
```

# Set Logger in Home Assistant

To setup logger for this custom component add following lines to configuration.yaml

```
logger:
  default: warn
  logs:
    custom_components.wibeee.sensor: info
```

Possible log levels: info, debug, warn, ...

# Example View in Home Assistant

![hass_view](https://i.imgur.com/PL3Qr4L.png "Example View in Home Assistant")

# Useful links

Home Assistant community
https://community.home-assistant.io/t/new-integration-energy-monitoring-device-circutor-wibeee/45276
