# Lens To-Do List

### Session management
- [X] Handle new session through tab updates and not just in cookie change
- [X] Handle session termination
- [X] Add tab tracking and log duration in each chart separately
- [X] Finalize daily usage persistance with debouncing 
- [X] Refactor session manager to handle both user sessions and chart sessions
- [X] Figure out why sum of chart usages does not accumulate to daily usage (I would expect the opposite)
- [ ] Manage chart session life cycle by tracking active tabs
 
### Utilities
- [ ] Improve the logging to be more strucutred and support levels
- [ ] Granular save and load of session state and session logs

### Content script
- [X] Remove redundant message sent string
- [X] Review on click, we might avoid it
- [X] Filter hosts by pcc subdomains (e.g. filter login out)
- [ ] Handle MDS section V
- [-] Programatically inject the content script into existing tabs on installation (low priority)
- [ ] Support Admin charts (currently only clinical)

### Side panel
- [X] Refresh logs and sessions
- [X] Fix the session logs to show only seconds
- [X] Fix filtering on user and org
- [X] Show session logs in a table
- [X] Session log filtering
- [X] Close the panel when swithcing to non permitted page
- [X] Write logs to Google spreadsheet and allow setting its
- [X] Session log clear
- [X] Protect speadsheet ID from changing by mistake
- [ ] Allow granular deletion (low priority)

### General
- [ ] README file