# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]
- `deepfellow infra status` / `deepfelow server status` - displays container status and resource usage

## [0.1.0] - 2026-01-16

### Added
- Initial release of DeepFellow CLI
- Server management commands:
  - `deepfellow server install` - Install DeepFellow Server with docker
  - `deepfellow server start` - Start DeepFellow Server
  - `deepfellow server stop` - Stop DeepFellow Server
  - `deepfellow server update` - Update DeepFellow Server
  - `deepfellow server login` - Login user and store the token in the secrets file
  - `deepfellow server create-admin` - Create admin
  - `deepfellow server password-reset` - Password reset
  - `deepfellow server opentelemetry` - Connect to Open Telemetry
  - `deepfellow server project` - Manage Projects
  - `deepfellow server organization` - Manage Organizations
  - `deepfellow server env` - Manage DeepFellow Server environment variables
  - `deepfellow server info` - Display environment configuration
- Infra management commands:
  - `deepfellow infra install` - Install infra with docker
  - `deepfellow infra start` - Start DeepFellow Infra
  - `deepfellow infra stop` - Stop DeepFellow Infra
  - `deepfellow infra update` - Update DeepFellow Infra
  - `deepfellow infra ssl-on` - Switch on the SSL
  - `deepfellow infra connect` - Connect two Infras together
  - `deepfellow infra disconnect` - Disconnect infra
  - `deepfellow infra service` - Manage DeepFellow Infra services
  - `deepfellow infra model` - Manage DeepFellow Infra models
  - `deepfellow infra env` - Manage Infra environment variables
  - `deepfellow infra info` - Display environment configuration
- Support for Docker Compose features
- Environment variable management for both server and infra
- OpenTelemetry integration support for server installations
- Project and organization management capabilities
- Password reset functionality
- Admin creation support
- Service and model management for infra
- SSL configuration support
- Environment configuration and management
