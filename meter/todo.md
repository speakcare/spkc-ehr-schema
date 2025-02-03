# Lens To-Do List

### Session management
- [X] Handle new session through tab updates and not just in cookie change
- [X] Handle session termination
- [ ] Add tab tracking and log durating in each chart separately
- [ ] Finalize daily usage persistance with debouncing 
- [ ] Refactor session manager to handle both user sessions and chart sessions
- [ ] Manage chart session life cycle by tracking active tabs
 
### Utilities
- [ ] Improve the logging to be more strucutred and support levels
- [ ] Granular save and load of session state and session logs

### Content script
- [ ] Remove redundant message sent string
- [X] Filter hosts by pcc subdomains (e.g. filter login out)
- [ ] Programatically inject the content script into existing tabs on installation (low priority)
- [ ] Support Admin charts (currently only clinical)

### Side panel
- [X] Refresh logs and sessions
- [X] Fix the session logs to show only seconds
- [ ] Fix filtering on user and org
- [X] Show session logs in a table
- [X] Session log filtering
- [X] Close the panel when swithcing to non permitted page
- [ ] Write logs to Google spreadsheet and allow setting its
- [X] Session log clear
- [ ] Allow granular deletion (low priority)

### General
- [ ] README file