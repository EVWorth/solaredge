Introduction 
The SolarEdge API allows other software applications to access its monitoring system database for data analysis purposes, fleet 
management, displaying system data in other applications, etc. 
The following is a list of available APIs: 
API Name | API Output 
Site List | A list of sites for a given account, with the information on each site. This list allows convenient search, sort and pagination 
Site Details | Details of a chosen site 
Site Data: Start and End Dates | The site energy production start and end dates 
Site Energy | Site energy measurements 
Site Energy – Time Period | Site energy for a requested timeframe 
Site Power | Site power measurements in a 15-minute resolution 
Site Overview | Site current power, energy production (today, this month, lifetime) and lifetime revenue 
Site Power | Detailed site power measurements including meters such as consumption, export (feed-in), import (purchase), etc. 
Site Energy | Detailed site energy measurements including meters such as consumption, export (feed-in), import (purchase), etc. 
Site Power Flow | Get the power flowchart of the site 
Storage | Get detailed storage information from batteries including the state of energy, power and lifetime energy 
Site Image | The site image as uploaded to the server, either scaled or original size 
Site Environmental Benefits | Summary of site’s positive impact on the environment
Installer Logo Image | The installer logo image as uploaded to the server. 
Components List | List of inverters with name, model, manufacturer, serial number and status 
Inventory | Information about the SolarEdge equipment, including: inverters/SMIs, batteries, meters, gateways and sensors 
Inverter Technical Data | Technical data on the inverter performance for a requested period of time 
Equipment Change Log | List of replacements for a given component 
Account List API | The account details and list of all sub-accounts 
Get Sensor List | The list of sensors installed in the site 
Get Sensor Data | The measurements of the sensors installed in the site 
Get Meters Data | Information about each meter in the site including: lifetime energy, metadata and the device to which it’s connected to. 
API Versions | The current and supported version numbers 

Note: a more detailed developer reference has been added at `docs/SE_monitoring_API.md` — use that file for endpoint examples, parameter lists, and throttling guidance.


Daily Limitation 
Use of the monitoring server API is subject to a query limit of 300 requests for a specific account token and a parallel query limit 
of 300 requests for each specific site ID from the same source IP. 
APIs that do not have a specific ID (e.g. Site List, Account List) will be counted as part of the account query limit. 
Any additional site or account level request will result in HTTP 429 error – too many requests. 



Concurrency Limitation 
The monitoring server API allows up to 3 concurrent API calls from the same source IP. Any additional concurrent calls will return 
HTTP 429 error – too many requests. 
To execute APIs concurrently without exceeding the above limitation, it is the client responsibility to implement a throttling 
mechanism on the client side. 



Bulk Use 
Some of the APIs offer a bulk form, that is, they take multiple site IDs as an input. The list is separated by a comma and should 
contain up to 100 site IDs. 
A bulk call for multiple sites consumes 1 call from the daily quota allowed for each of the sites included in the call. 

