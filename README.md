[![hacs_badge](https://img.shields.io/badge/HACS-Default-yellow.svg?style=for-the-badge)](https://github.com/custom-components/hacs) [![GitHub release (latest by date)](https://img.shields.io/github/v/release/luuuis/hass_wibeee?label=Latest%20release&style=for-the-badge)](https://github.com/luuuis/hass_wibeee/releases) [![GitHub all releases](https://img.shields.io/github/downloads/luuuis/hass_wibeee/total?style=for-the-badge)](https://github.com/luuuis/hass_wibeee/releases)

# Home Assistant: Wibeee (and Mirubee) energy monitor custom component

<img src="https://github.com/luuuis/hass_wibeee/assets/161006/f0a2e9c5-0f1c-46ee-b87b-b150c0f6f84b" width="300" alt="Wibeee logo"/>

## Features

Integrates CIRCUTOR Wibeee/Mirubee energy monitoring devices into Home Assistant. Works with single and three-phase
versions.

### Sensors

Provides the following sensors, one for each circuit using `l1`/`l2`/`l3` in the name and entity id. For three-phase
devices there is an additional device and set of sensors containing the total readings across all phases.

| Sensor                                            | Unit | Description                |
|---------------------------------------------------|:----:|----------------------------|
| `wibeee_<mac_addr>_l1_active_energy`              |  Wh  | Active Energy              |
| `wibeee_<mac_addr>_l1_active_energy_produced`     |  Wh  | Active Energy Produced     |
| `wibeee_<mac_addr>_l1_active_energy_consumed`     |  Wh  | Active Energy Consumed     |
| `wibeee_<mac_addr>_l1_active_power`               |  W   | Active Power               |
| `wibeee_<mac_addr>_l1_apparent_power`             |  VA  | Apparent Power             |
| `wibeee_<mac_addr>_l1_capacitive_reactive_energy` | varh | Capacitive Reactive Energy |
| `wibeee_<mac_addr>_l1_capacitive_reactive_power`  | var  | Capacitive Reactive Power  |
| `wibeee_<mac_addr>_l1_frequency`                  |  Hz  | Frequency                  |
| `wibeee_<mac_addr>_l1_inductive_reactive_energy`  | varh | Inductive Reactive Energy  |
| `wibeee_<mac_addr>_l1_inductive_reactive_power`   | var  | Inductive Reactive Power   |
| `wibeee_<mac_addr>_l1_reactive_power`             | var  | Reactive Power             |
| `wibeee_<mac_addr>_l1_current`                    |  A   | Current                    |
| `wibeee_<mac_addr>_l1_power_factor`               |  PF  | Power Factor               |
| `wibeee_<mac_addr>_l1_phase_voltage`              |  V   | Phase Voltage              |


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
See [Sensor Examples](https://github.com/luuuis/hass_wibeee/wiki/Sensor-Examples)
for suggested sensors that will help you get the most out of the integration.

### 💡 Configuring Local Push (optional, advanced)

Local Push is highly recommended for increased stability and performance. Normally the integration will poll your devices to refresh the sensors but this should not be done too frequently to avoid overloading the device's remote API, which can cause the device to hang. With some extra configuration on the device it is possible to set up Local Push support, meaning that the device will push the sensor data to Home Assistant with high frequency (about every 10 seconds but more or less frequently as necessary).

1. In the integration's configuration under `Cloud service to upload data to` select one of the available options that causes the integration to listen on **port 8600** for Local Push updates from your Wibeee device.
   * Choose **Local only** and the integration will listen for local push updates and will store them locally,
   * Choose **Wibeee Nest** and the integration will listen for local push updates and will send them to Wibeee Nest after storing them locally,
   * and similar for other Cloud services such as Iberdrola and SolarProfit.

    ![Wibee integration polling interval configuration](https://github.com/luuuis/hass_wibeee/assets/161006/87309a25-2ee3-4658-8662-61ab0a068234) ![Wibee integration local push configuration](https://github.com/luuuis/hass_wibeee/assets/161006/dc047ecc-743b-43a9-a3a8-fea9660c7775)

   The polling interval should be set much higher when Local Push is in use. Updates are sent by the Wibeee device with high frequency so there is no reason for a short polling interval that will overload the device.
   
4. Open the device UI and in **Advanced Options** update the **Server** section to contain the IP address of your Home Assistant.
  
    ![Wibeee Web UI](https://community-assets.home-assistant.io/original/4X/3/4/d/34d66a091cd79ce4d12b5a9cf53f41e4c4b49612.jpeg)
  
    **Default**: Server URL is `nest-ingest.wibeee.com` and Server Port is 80  
    **After**: Server URL the IP address of your HA instance and Server Port is 8600

    Click **Apply** to make Wibeee restart, after which it should start pushing data to the Wibeee integration within Home Assistant.

If everything was done correctly sensor data should now update [every second in Home Assistant and Wibeee Nest](https://community.home-assistant.io/t/new-integration-energy-monitoring-device-circutor-wibeee/45276/257?u=luuuis).

# Example View in Home Assistant

<img src="https://user-images.githubusercontent.com/161006/147989082-2f45b4cf-84cf-4915-82ad-fcf09886e85b.jpg" alt="Wibeee Device view in Home Assistant" width="400"/>

<img src="https://user-images.githubusercontent.com/161006/148742540-01d0a802-9040-44ad-86c4-af8eff92838d.jpg" alt="Active Power graph in Home Assistant" width="400"/>
