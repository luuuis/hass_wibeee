[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/hacs/integration)  

# Home Assistant: Wibeee (and Mirubee) energy monitor custom component
<img src="https://wibeee.com/wp-content/uploads/2018/09/logo.png" width="200" alt="Wibeee logo"/>

## Features

Integrates CIRCUTOR Wibeee/Mirubeee energy monitoring devices into Home Assistant. Works
with single and three-phase versions.

### Sensors
Provides the following sensors, one for each phase (`Phase1` shown below).

| Sensor                                     | Unit  | Description       |
| -------------------------------------------|:------:|------------------|
| `wibeee_Phase1_active_energy`              | Wh    | Active Energy |
| `wibeee_Phase1_active_power`               | W     | Active Power |
| `wibeee_Phase1_apparent_power`             | VA    | Apparent Power |
| `wibeee_Phase1_capacitive_reactive_energy` | VArCh | Capacitive Reactive Energy |
| `wibeee_Phase1_capacitive_reactive_power`  | VArC  | Capacitive Reactive Power |
| `wibeee_Phase1_frequency`                  | Hz    | Frequency |
| `wibeee_Phase1_inductive_reactive_energy`  | VArLh | Inductive Reactive Energy |
| `wibeee_Phase1_inductive_reactive_power`   | VArL  | Inductive Reactive Power |
| `wibeee_Phase1_irms`                       | A     | Current |
| `wibeee_Phase1_power_factor`               | PF    | Power Factor |
| `wibeee_Phase1_vrms`                       | V     | Phase Voltage |

In three-phased devices `Phase4` sensors contain the total readings across all three phases.

## Installation

Use [HACS](https://hacs.xyz) (preferred) or follow the manual instructions below.

### Installation with HACS

Custom repository installation:
1. Open `Integrations` inside the HACS configuration.
3. In the top right corner, click on the 3 dots and select `Custom repositories`
4. Add the custom repository URL https://github.com/luuuis/hass_wibeee and select `Integration` as
   the category in the list, then click `Add`.
5. Click the + button in the bottom right corner, select this Wibeee component and `Install this repository in HACS`.
6. Once installation is complete, restart Home Assistant

### Manual installation

1. Download `hass_wibeee.zip` from the latest release in https://github.com/luuuis/hass_wibeee/releases/latest
2. Unzip into `<hass_folder>/config/custom_components`
    ```shell
    $ unzip hass_wibeee.zip -d <hass_folder>/custom_components/wibeee
    ```
3. Restart Home Assistant

# Configuration
Add device to home assistant configuration file configuration.yaml and provide the IP address
of the energy monitor on your network.

```yaml
sensor:
- platform: wibeee
  host: 192.168.xx.xx # use static IP
```
 
Optionally, configure extra template sensors for grid consumption and feed-in to use
with [Home Energy Management](https://www.home-assistant.io/home-energy-management/). 

# Example View in Home Assistant

<img src="https://i.imgur.com/PL3Qr4L.png" alt="Example View in Home Assistant" width="400"/>

# Useful links

Home Assistant Community thread:
https://community.home-assistant.io/t/new-integration-energy-monitoring-device-circutor-wibeee/45276
