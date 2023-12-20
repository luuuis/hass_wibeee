# Changelog

All notable changes to this project will be documented in this file. See [standard-version](https://github.com/conventional-changelog/standard-version) for commit guidelines.

## [3.4.0-beta.4](https://github.com/luuuis/hass_wibeee/compare/v3.4.0-beta.3...v3.4.0-beta.4) (2023-12-19)

## [3.4.0-beta.3](https://github.com/luuuis/hass_wibeee/compare/v3.4.0-beta.2...v3.4.0-beta.3) (2023-12-19)


### Bug Fixes

* **api:** async_fetch_status correctly handles values2.xml response try 2 ([4ebad05](https://github.com/luuuis/hass_wibeee/commit/4ebad056a6815244845380e7927f76eecc512f96))

## [3.4.0-beta.2](https://github.com/luuuis/hass_wibeee/compare/v3.4.0-beta.1...v3.4.0-beta.2) (2023-12-19)


### Bug Fixes

* **api:** async_fetch_status correctly handles values2.xml response ([df4be77](https://github.com/luuuis/hass_wibeee/commit/df4be7775de91a855e923f50fc39192b71711584))

## [3.4.0-beta.1](https://github.com/luuuis/hass_wibeee/compare/v3.4.0-beta.0...v3.4.0-beta.1) (2023-12-19)


### Bug Fixes

* **api:** API address is /services/user/values2.xml ([6922437](https://github.com/luuuis/hass_wibeee/commit/692243738ed83bad61ad43cd7061a7395b3247c8))

## [3.4.0-beta.0](https://github.com/luuuis/hass_wibeee/compare/v3.3.0...v3.4.0-beta.0) (2023-12-18)


### Features

* **api:** support values2.xml API used by firmware >= 4.4.171 ([2b0577c](https://github.com/luuuis/hass_wibeee/commit/2b0577c4e7e0a15189200ae49f396aa1b8b065cb))

## [3.3.0](https://github.com/luuuis/hass_wibeee/compare/v3.2.4...v3.3.0) (2023-09-25)


### Features

* add configuration option to change the upstream URL ([#62](https://github.com/luuuis/hass_wibeee/issues/62)) ([bb596f6](https://github.com/luuuis/hass_wibeee/commit/bb596f66832d42c72d01ea99afdac2e49ee5fdfe))

### [3.2.4](https://github.com/luuuis/hass_wibeee/compare/v3.2.3...v3.2.4) (2023-03-09)


### Bug Fixes

* update the IP or hostname when adding a device that's already configured ([#60](https://github.com/luuuis/hass_wibeee/issues/60)) ([8f802c2](https://github.com/luuuis/hass_wibeee/commit/8f802c217aee0483f0c274d16c475e508afb18ee))

### [3.2.3](https://github.com/luuuis/hass_wibeee/compare/v3.2.2...v3.2.3) (2023-02-27)


### Bug Fixes

* remove power factor unit to clear HA warning ([#58](https://github.com/luuuis/hass_wibeee/issues/58)) ([7f33a93](https://github.com/luuuis/hass_wibeee/commit/7f33a9391ccd802d56fa9fc2d0c6dbf9bd456fc2))

### [3.2.2](https://github.com/luuuis/hass_wibeee/compare/v3.2.1...v3.2.2) (2022-10-05)


### Bug Fixes

* correctly assign phase 4 / total values from (Nest) Local Push updates ([#47](https://github.com/luuuis/hass_wibeee/issues/47)) ([cf121e3](https://github.com/luuuis/hass_wibeee/commit/cf121e379cc609e3686b3e76253f20ff2925f555))

### [3.2.1](https://github.com/luuuis/hass_wibeee/compare/v3.2.0...v3.2.1) (2022-09-22)


### Bug Fixes

* update device and state class constants ([#21](https://github.com/luuuis/hass_wibeee/issues/21)) ([af4bd7a](https://github.com/luuuis/hass_wibeee/commit/af4bd7a0afb1a73c4b9f021836ccdfe09cdca2f9))

## [3.2.0](https://github.com/luuuis/hass_wibeee/compare/v3.1.2...v3.2.0) (2022-08-29)


### Features

* add nest proxy for Local Push support ([#39](https://github.com/luuuis/hass_wibeee/issues/39)) ([cae89ec](https://github.com/luuuis/hass_wibeee/commit/cae89ec59720805bfb5107215b64e766ed7ffbd7))

### [3.1.2](https://github.com/luuuis/hass_wibeee/compare/v3.1.1...v3.1.2) (2022-02-07)


### Bug Fixes

* energy sensors use `state_class: total_increasing` ([#34](https://github.com/luuuis/hass_wibeee/issues/34)) ([36a9a48](https://github.com/luuuis/hass_wibeee/commit/36a9a4889b7e7d2bfedc59c75f91c232d38c0edc))

### [3.1.1](https://github.com/luuuis/hass_wibeee/compare/v3.1.0...v3.1.1) (2022-01-07)


### Bug Fixes

* abort import of configuration.yaml entry if already imported ([#30](https://github.com/luuuis/hass_wibeee/issues/30)) ([c71c91a](https://github.com/luuuis/hass_wibeee/commit/c71c91a5ba1d15c5b41b062668dd28e88819e938))

## [3.1.0](https://github.com/luuuis/hass_wibeee/compare/v3.0.0...v3.1.0) (2022-01-03)


### Features

* implement device info for Wibeee sensors ([#26](https://github.com/luuuis/hass_wibeee/issues/26)) ([7938ea4](https://github.com/luuuis/hass_wibeee/commit/7938ea40577b18d0340f2804c79fadbe935ad906))


### Bug Fixes

* set HTTP errors to DEBUG level when they are going to be retried ([#25](https://github.com/luuuis/hass_wibeee/issues/25)) ([b3967f7](https://github.com/luuuis/hass_wibeee/commit/b3967f7c425bf228e7f59840b70bd374ec58bda3))

## [3.0.0](https://github.com/luuuis/hass_wibeee/compare/v2.2.3...v3.0.0) (2022-01-02)

Adds multiple device support. All entities now have a `unique_id`, which 
allows them to be customised and renamed in Home Assistant.

### ⚠ BREAKING CHANGES

* sets `unique_id` on entities, which causes HA to create new entities.
* YAML configuration is no longer supported. Existing configuration is imported as a one-off.

### Features

* add config flow for integration UI ([#22](https://github.com/luuuis/hass_wibeee/issues/22)) ([d4782d7](https://github.com/luuuis/hass_wibeee/commit/d4782d77f5ecb837515ee909fdb3ca38a4922284))
* generate entity unique_id from MAC address ([#12](https://github.com/luuuis/hass_wibeee/issues/12)) ([1f8b966](https://github.com/luuuis/hass_wibeee/commit/1f8b966612b3acfb296acde5975fd96d66f3ce9b))
* implement config options to allow changing scan_interval ([#23](https://github.com/luuuis/hass_wibeee/issues/23)) ([cbf76b0](https://github.com/luuuis/hass_wibeee/commit/cbf76b02d342c04debcde4d0468765cdc4fa8460))
* use human-friendly name for sensors with unique_id, otherwise keep the old name ([#13](https://github.com/luuuis/hass_wibeee/issues/13)) ([bb59ccb](https://github.com/luuuis/hass_wibeee/commit/bb59ccbe518264c336c465ad5fd34521cbac0b12))
* use Wibeee device name to assign Home Assistant name ([#18](https://github.com/luuuis/hass_wibeee/issues/18)) ([da3174c](https://github.com/luuuis/hass_wibeee/commit/da3174c1e9704fe816f533ef359d8469b738e380))


### Bug Fixes

* don't update entities that are disabled ([#15](https://github.com/luuuis/hass_wibeee/issues/15)) ([6474db6](https://github.com/luuuis/hass_wibeee/commit/6474db64ae02642b8e40b5df331d093181401b07))

### [2.2.3](https://github.com/luuuis/hass_wibeee/compare/v2.2.2...v2.2.3) (2021-08-31)


### Bug Fixes

* make sensors unavailable on status.xml error ([#10](https://github.com/luuuis/hass_wibeee/issues/10)) ([79dc987](https://github.com/luuuis/hass_wibeee/commit/79dc987ec24cfe75d2c254584703e79a82866120))

### [2.2.2](https://github.com/luuuis/hass_wibeee/compare/v2.2.1...v2.2.2) (2021-08-28)


### Bug Fixes

* retry failed requests with exponential backoff ([#9](https://github.com/luuuis/hass_wibeee/issues/9)) ([2fa3e6c](https://github.com/luuuis/hass_wibeee/commit/2fa3e6c3a8c0ca0dc3e395b5cd1b5037949f2acf))

### [2.2.1](https://github.com/luuuis/hass_wibeee/compare/v2.2.0...v2.2.1) (2021-08-25)


### Bug Fixes

* don't error with "Unable to create WibeeeSensor" on unknown keys ([#7](https://github.com/luuuis/hass_wibeee/issues/7)) ([a8d75c3](https://github.com/luuuis/hass_wibeee/commit/a8d75c38cf4b138c065d56187257a58f92ac8559))
* improve error logging to allow bug reports ([#8](https://github.com/luuuis/hass_wibeee/issues/8)) ([3d0297e](https://github.com/luuuis/hass_wibeee/commit/3d0297e969593fd076af3b92aa84b366224b9261))

## [2.2.0](https://github.com/luuuis/hass_wibeee/compare/v2.1.0...v2.2.0) (2021-08-25)


### Features

* add scan_interval support to allow this to be user-configured ([#6](https://github.com/luuuis/hass_wibeee/issues/6)) ([34f4019](https://github.com/luuuis/hass_wibeee/commit/34f401923d389f17f3c8b35ce3b72308a0b26e27))

## [2.1.0](https://github.com/luuuis/hass_wibeee/compare/v2.0.0...v2.1.0) (2021-08-24)


### Features

* Energy support ([#5](https://github.com/luuuis/hass_wibeee/issues/5)) ([113e60e](https://github.com/luuuis/hass_wibeee/commit/113e60ef10666f017c4fdfec54a6dc28ac525bde))


### Bug Fixes

* clean up WibeeeSensor attrs ([#4](https://github.com/luuuis/hass_wibeee/issues/4)) ([4859014](https://github.com/luuuis/hass_wibeee/commit/485901464706fbe2b2b0d52839364d6a924e7d23))

### [2.0.1](https://github.com/luuuis/hass_wibeee/compare/v2.0.0...v2.0.1) (2021-08-22)


### Bug Fixes

* removes WibeeeSensor `icon` and `unique_id` ([5230596](https://github.com/luuuis/hass_wibeee/commit/5230596b14277f7df5932fb9ca3c3e28552284a0))

## 2.0.0 (2021-08-22)


### Bug Fixes

* specify `iot_class` for custom component, add hassfest workflow ([#1](https://github.com/luuuis/hass_wibeee/issues/1)) ([6a5c9c8](https://github.com/luuuis/hass_wibeee/commit/6a5c9c86c104bb32ccb7fff3da0086fc898b4446))
