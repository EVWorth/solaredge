import requests
import datetime as dt
from functools import wraps
import pytz
import numbers

__title__ = "solaredge"
__version__ = "0.0.1"
__author__ = "Bert Outtier"
__license__ = "MIT"

BASEURL = 'https://monitoringapi.solaredge.com'

class Solaredge(object):
    """
    Object containing SolarEdge's site API-methods.
    See https://www.solaredge.com/sites/default/files/se_monitoring_api.pdf
    """
    def __init__(self, site_token):
        """
        To communicate, you need to set a site token.
        Get it from your account.

        Parameters
        ----------
        site_token : str
        """
        self.token = site_token

    def get_list(self, size=100, startIndex=0, searchText="", sortProperty="", sortOrder='ASC', status='Active,Pending'):
        """
        Request service locations

        Returns
        -------
        dict
        """

        url = urljoin(BASEURL, "sites", "list")

        params = {
            'api_key': self.token,
            'size': size,
            'startIndex': startIndex,
            'sortOrder': sortOrder,
            'status': status
        }

        if searchText:
            params['searchText'] = searchText

        if sortProperty:
            params['sortProperty'] = sortProperty

        r = requests.get(url, params)
        r.raise_for_status()
        return r.json()


    def get_details(self, site_id):
        """
        Request service location info

        Parameters
        ----------
        site_id : int

        Returns
        -------
        dict
        """
        url = urljoin(BASEURL, "site", site_id, "details")
        params = {
            'api_key': self.token
        }
        r = requests.get(url, params)
        r.raise_for_status()
        return r.json()


    def get_dataPeriod(self, site_id):
        """
        Request service location info

        Parameters
        ----------
        site_id : int

        Returns
        -------
        dict
        """
        url = urljoin(BASEURL, "site", site_id, "dataPeriod")
        params = {
            'api_key': self.token
        }
        r = requests.get(url, params)
        r.raise_for_status()
        return r.json()


    def get_energy(self, site_id, startDate, endDate, timeUnit='DAY'):
        url = urljoin(BASEURL, "site", site_id, "energy")
        params = {
            'api_key': self.token,
            'startDate': startDate,
            'endDate': endDate,
            'timeUnit': timeUnit
        }
        r = requests.get(url, params)
        r.raise_for_status()
        return r.json()

    def get_timeFrameEnergy(self, site_id, startDate, endDate, timeUnit='DAY'):
        url = urljoin(BASEURL, "site", site_id, "timeFrameEnergy")
        params = {
            'api_key': self.token,
            'startDate': startDate,
            'endDate': endDate,
            'timeUnit': timeUnit
        }
        r = requests.get(url, params)
        r.raise_for_status()
        return r.json()


    def get_power(self, site_id, startTime, endTime):
        url = urljoin(BASEURL, "site", site_id, "power")
        params = {
            'api_key': self.token,
            'startTime': startTime,
            'endTime': endTime
        }
        r = requests.get(url, params)
        r.raise_for_status()
        return r.json()


    def get_overview(self, site_id):
        url = urljoin(BASEURL, "site", site_id, "overview")
        params = {
            'api_key': self.token
        }
        r = requests.get(url, params)
        r.raise_for_status()
        return r.json()

    def get_powerDetails(self, site_id, startTime, endTime, meters=None):
        url = urljoin(BASEURL, "site", site_id, "powerDetails")
        params = {
            'api_key': self.token,
            'startTime': startTime,
            'endTime': endTime
        }

        if meters:
            params['meters'] = meters

        r = requests.get(url, params)
        r.raise_for_status()
        return r.json()

    def get_energyDetails(self, site_id, startTime, endTime, meters=None, timeUnit="DAY"):
        url = urljoin(BASEURL, "site", site_id, "energyDetails")
        params = {
            'api_key': self.token,
            'startTime': startTime,
            'endTime': endTime,
            'timeUnit': timeUnit
        }

        if meters:
            params['meters'] = meters

        r = requests.get(url, params)
        r.raise_for_status()
        return r.json()

    def get_currentPowerFlow(self, site_id):
        url = urljoin(BASEURL, "site", site_id, "currentPowerFlow")
        params = {
            'api_key': self.token
        }

        r = requests.get(url, params)
        r.raise_for_status()
        return r.json()

    def get_storageData(self, site_id, startTime, endTime, serials=None):
        url = urljoin(BASEURL, "site", site_id, "storageData")
        params = {
            'api_key': self.token,
            'startTime': startTime,
            'endTime': endTime
        }

        if serials:
            params['serials'] = serials.join(',')

        r = requests.get(url, params)
        r.raise_for_status()
        return r.json()


def urljoin(*parts):
    """
    Join terms together with forward slashes

    Parameters
    ----------
    parts

    Returns
    -------
    str
    """
    # first strip extra forward slashes (except http:// and the likes) and
    # create list
    part_list = []
    for part in parts:
        p = str(part)
        if p.endswith('//'):
            p = p[0:-1]
        else:
            p = p.strip('/')
        part_list.append(p)
    # join everything together
    url = '/'.join(part_list)
    return url
