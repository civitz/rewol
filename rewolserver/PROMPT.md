This is rewol, the remote WOL service to do remote wake on lan with a proxy service.

Assume the remote proxy already exist with the following API:
- a GET /status API that responds with an HTTP 200 and a prometheus response that contains the following metrics:
    + rewol_service_uptime of the remote proxy service itself as millisecond gauge metric
    + rewol_host_up gauge metric, with an "host" label for each known host, that shows 1 if host is up
    + rewol_host_wol gauge metric, with an "host" label for each known host, that adds 1 each time the WOL signal is sent to the host

- a POST /wol API with a "host" and "password" parameters that
    + return HTTP 401 unauthorized if password is wrong
    + returns 404 not found if host is unknown 
    + responds with an HTTP 201 if it sends the WOL to the host

Create a webservice in python in one file called rewol.py .

The service is a frontpage for launching WOL to known hosts.

Assume one or more remote WOL proxy exist.

This is the sample configuration (taken from config.sample.yaml):
```yaml
backends:
  - host: "The first rewol proxy"
    address: "x.x.x.x" # the IP or address of the remote WOL proxy
    password: "" # the password for that remote proxy
  - host: "The second rewol proxy"
    address: "x.x.x.x" # the IP or address of the remote WOL proxy
    password: "" # the password for that remote proxy

service:
  # these are configuration of the rewolserver service
  # use generatepwdandsalt.py to calculate these
  password: "<base64 of the salted password>"
  salt: "<base64 of salt>"
  port: 5000
```
 
The service should show a page with:
- a list of hosts
   + each host has a name, a status, and an host name of the remote WOL proxy
   + the status is green if up (1) or red if down (0)
   + the page should be unprotected
- a button, next to each host that has a "down" status, to launch the WOL command via the POST /wol API to the corresponding server
   + clicking the button should ask for a password
   + the password is verified against service.password and service.salt configuration. Please see existing code for that.
   + the rewolproxy needs a password, the password for the proxy can be read in the configuration; for now it will be plaintext.


Use no javascript libraries please, but you can write javascript in the html file if you need.
No need for fancy UI

To construct the list of hosts the backend should:
- look at the configuration
- call the GET /status API for each rewolproxy
- extract the known hosts by parsing rewol_host_up metric of each rewolproxy
- use the list of hosts as a template variable
- if the rewolproxy is down, display an empty host line with "rewol proxy down" and the corresponding name and address
- assume no overlapping host

Logging should be carried with the "logging" python library.
It should print log to console.
It should also write a rotating log with a limit of 10 MB and 1 rotated file max.

An existing code exists and can be reused, but it is old and contains old requirements.
You can edit the code and the html templates.
For the frontend I suggest keeping only the status.html page and make it a single page app.

Any mention of:
- service link
- scripts
- stopping the service
Should be treated as old code and removed.

Detail a plan and discuss any missing requirement before implementing.
