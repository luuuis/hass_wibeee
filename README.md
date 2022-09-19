[![hacs_badge](https://img.shields.io/badge/HACS-Default-yellow.svg?style=for-the-badge)](https://github.com/custom-components/hacs) [![GitHub release (latest by date)](https://img.shields.io/github/v/release/luuuis/hass_wibeee?label=Latest%20release&style=for-the-badge)](https://github.com/luuuis/hass_wibeee/releases) [![GitHub all releases](https://img.shields.io/github/downloads/luuuis/hass_wibeee/total?style=for-the-badge)](https://github.com/luuuis/hass_wibeee/releases)

# Home Assistant: Wibeee (and Mirubee) energy monitor custom component

<img src="https://wibeee.com/wp-content/uploads/2018/09/logo.png" width="200" alt="Wibeee logo"/>

## Features

Integrates CIRCUTOR Wibeee/Mirubeee energy monitoring devices into Home Assistant. Works with single and three-phase
versions.

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

### Installation using HACS

1. Open `Integrations` inside the HACS configuration.
2. Click the + button in the bottom right corner, select `Wibeee (and Mirubee) energy monitor` and then `Install this repository in HACS`.
3. Once installation is complete, restart Home Assistant

<details>
  <summary>Manual installation instructions</summary>

### **Manual installation**

1. Download `hass_wibeee.zip` from the latest release in https://github.com/luuuis/hass_wibeee/releases/latest
2. Unzip into `<hass_folder>/config/custom_components`
    ```shell
    $ unzip hass_wibeee.zip -d <hass_folder>/custom_components/wibeee
    ```
3. Restart Home Assistant

</details>

# Configuration

Go to the `Integrations` page, click `Add Integration` and select the Wibeee integration or click the following button.

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=wibeee)

![Configuration - Home Assistant 2021-12-29 01-08-21](https://user-images.githubusercontent.com/161006/147618048-25206d88-6f41-43db-8e0b-2a6ad9be1770.jpg)

Enter the device's IP address and the integration will detect the meter's type before adding the relevant sensors to
Home Assistant.

![Configuration - Home Assistant 2021-12-29 01-09-26](https://user-images.githubusercontent.com/161006/147618112-cbf0890f-d36c-4509-9901-94b65cc69229.jpg)

Optionally, configure extra template sensors for grid consumption and feed-in to use
with [Home Energy Management](https://www.home-assistant.io/home-energy-management/).
See [SENSOR_EXAMPLES.md](./SENSOR_EXAMPLES.md)
for suggested sensors that will help you get the most out of the integration.

### Configuring Local Push (optional, advanced)

Normally the integration will poll your devices to refresh the sensors but this should not be done too frequently to avoid overloading the device's remote API, which can cause the device to hang. With some extra configuration on the device it is possible to set up Local Push support, meaning that the device will push the sensor data to Home Assistant, which then forwards it to Wibeee Nest.

1. Check the `Enable Nest Proxy on port 8600` option in the integration to allow Home Assistant to listen for sensor updates from your Wibeee device.
  
    ![Wibee integration configuration](https://community-assets.home-assistant.io/original/4X/a/9/a/a9a0af1900f1b151fa5e79d6c885c8dad2898cb1.jpeg)

2. Open the device UI and in **Advanced Options** update the **Server** section to contain the IP address of your Home Assistant.
  
    ![Wibeee Web UI](https://community-assets.home-assistant.io/original/4X/3/4/d/34d66a091cd79ce4d12b5a9cf53f41e4c4b49612.jpeg)
  
    **Default**: Server URL is `nest-ingest.wibeee.com` and Server Port is 80  
    **After**: Server URL the IP address of your HA instance and Server Port is 8600

    Click **Apply** to make Wibeee restart, after which it should start pushing data to the Wibeee integration within Home Assistant.

If everything was done correctly sensor data should now update [every second in Home Assistant and Wibeee Nest](https://community.home-assistant.io/t/new-integration-energy-monitoring-device-circutor-wibeee/45276/257?u=luuuis).

# Example View in Home Assistant

<img src="https://user-images.githubusercontent.com/161006/147989082-2f45b4cf-84cf-4915-82ad-fcf09886e85b.jpg" alt="Wibeee Device view in Home Assistant" width="400"/>

<img src="https://user-images.githubusercontent.com/161006/148742540-01d0a802-9040-44ad-86c4-af8eff92838d.jpg" alt="Active Power graph in Home Assistant" width="400"/>
