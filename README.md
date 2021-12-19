[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/hacs/integration) [![GitHub release (latest by date)](https://img.shields.io/github/v/release/luuuis/hass_wibeee?label=Latest%20release&style=for-the-badge)](https://github.com/luuuis/hass_wibeee/releases) [![GitHub all releases](https://img.shields.io/github/downloads/luuuis/hass_wibeee/total?style=for-the-badge)](https://github.com/luuuis/hass_wibeee/releases)
# Home Assistant: Wibeee (and Mirubee) energy monitor custom component
<img src="https://wibeee.com/wp-content/uploads/2018/09/logo.png" width="200" alt="Wibeee logo"/>

## Features

Integrates CIRCUTOR Wibeee/Mirubeee energy monitoring devices into Home Assistant. Works
with single and three-phase versions.

### Sensors

Provides the following sensors, one for each clamp using `_L1`/`_L2`/`_L3` suffixes.

| Sensor                                         | Unit  | Description       |
| -----------------------------------------------|:------:|------------------|
| `wibeee_<mac_addr>_active_energy`              | Wh    | Active Energy |
| `wibeee_<mac_addr>_active_power`               | W     | Active Power |
| `wibeee_<mac_addr>_apparent_power`             | VA    | Apparent Power |
| `wibeee_<mac_addr>_capacitive_reactive_energy` | VArCh | Capacitive Reactive Energy |
| `wibeee_<mac_addr>_capacitive_reactive_power`  | VArC  | Capacitive Reactive Power |
| `wibeee_<mac_addr>_frequency`                  | Hz    | Frequency |
| `wibeee_<mac_addr>_inductive_reactive_energy`  | VArLh | Inductive Reactive Energy |
| `wibeee_<mac_addr>_inductive_reactive_power`   | VArL  | Inductive Reactive Power |
| `wibeee_<mac_addr>_current`                    | A     | Current |
| `wibeee_<mac_addr>_power_factor`               | PF    | Power Factor |
| `wibeee_<mac_addr>_phase_voltage`              | V     | Phase Voltage |

In three-phase devices the `_L4` sensors contain the total readings across all phases.

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
  host: 192.168.1.xx # use static IP
  scan_interval: 15  # optional, defaults to 15 seconds
- platform: wibeee
  host: 192.168.1.yy # add a second device
```

Optionally, configure extra template sensors for grid consumption and feed-in to use
with [Home Energy Management](https://www.home-assistant.io/home-energy-management/). See [SENSOR_EXAMPLES.md](./SENSOR_EXAMPLES.md)
for suggested sensors that will help you get the most out of the integration.  

### Logging

To set up the logger for this custom component add following lines to configuration.yaml

```yaml
logger:
  default: warn
  logs:
    custom_components.wibeee.sensor: info
```

Possible log levels: `info`, `debug`, `warn`, `error`.

# Example View in Home Assistant

<img src="https://i.imgur.com/PL3Qr4L.png" alt="Example View in Home Assistant" width="400"/>

# Useful links

Home Assistant Community thread:
https://community.home-assistant.io/t/new-integration-energy-monitoring-device-circutor-wibeee/45276/176
