# Solaredge
API wrapper for Solaredge monitoring service.

See https://www.solaredge.com/sites/default/files/se_monitoring_api.pdf

## Create a new connection by supplying your Solaredge API key
``` python
s = solaredge.Solaredge("APIKEY")
```

## API Requests
11 API requests are supported. The methods return the parsed JSON response as a dict.

``` python
def get_list(self, size=100, startIndex=0, searchText="", sortProperty="", sortOrder='ASC', status='Active,Pending'):

def get_details(self, site_id):

def get_data_period(self, site_id):

def get_energy(self, site_id, startDate, endDate, timeUnit='DAY'):

def get_time_frame_energy(self, site_id, startDate, endDate, timeUnit='DAY'):

def get_power(self, site_id, startTime, endTime):

def get_overview(self, site_id):

def get_power_details(self, site_id, startTime, endTime, meters=None):

def get_energy_details(self, site_id, startTime, endTime, meters=None, timeUnit="DAY"):

def get_current_power_flow(self, site_id):

def get_storage_data(self, site_id, startTime, endTime, serials=None):
```

## Usage example
``` python
import solaredge
import datetime

apikey = 'XXXXXXXXXXXX'
site_id = 'XXXXXXX'

api = solaredge.Solaredge(apikey)

lists = api.get_list(site_id)
details = api.get_details(site_id)['details']
dataperiod = api.get_data_period(site_id)
overview = api.get_overview(site_id)["overview"]
currentpowerflow =api.get_currentPowerFlow(site_id)

# get total dateframe
start_date = dataperiod['dataPeriod']['startDate']
end_date = dataperiod['dataPeriod']['endDate']

# per day data
energy = api.get_energy(site_id, start_date, end_date)
timeframeenergy = api.get_time_frame_energy(site_id, start_date, end_date)

# calculate timeframe
start_time = (datetime.datetime.now() - datetime.timedelta(hours = 1)).strftime('%Y-%m-%d %H:%M:%S')
end_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# per time data
power = api.get_power(site_id ,start_time, end_time)
powerdetails =api.get_power_details(site_id, start_time, end_time)
energydetails =api.get_energy_details(site_id, start_time, end_time)
storagedata =api.get_storage_data(site_id, start_time, end_time)

```

## TODO
* Add support for bulk requests
* Add API documentation
