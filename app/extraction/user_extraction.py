"""
Copyright (c) 2020-present SMC Treviso s.r.l. All rights reserved.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import threading
import logging
from datetime import datetime
from typing import Optional
from requests.auth import HTTPBasicAuth
import json
import time
import requests

N_RETRY = 10
RETRY_TIMEOUT = 10
TIMEOUT = 10
N_MAX_ERRORS = 30


class AsyncUserExtraction(threading.Thread):
    """Change Async task parameters with yours"""

    def __init__(self, domain, username, password, timestamp, company_id, datasource_id, ingestion_url):

        super(AsyncUserExtraction, self).__init__()
        self.domain = domain
        self.username = username
        self.password = password
        self.timestamp = timestamp
        self.companyId = company_id
        self.datasource_id = datasource_id
        self.ingestion_url = ingestion_url

        self.status = "RUNNING"

        self.status_logger = logging.getLogger("status-logger")

        self.basic_auth = HTTPBasicAuth(self.username, self.password)

        self.n_retry = N_RETRY
        self.retry_timeout = RETRY_TIMEOUT
        self.timeout = TIMEOUT
        self.n_max_errors = N_MAX_ERRORS

    def call_extraction_api(self, url, payload):
        """Use this function to call external extraction APIs installed on your data source. It implements a retry logic
        in case of an error.
            """

        for i in range(self.n_retry):
            try:
                r = requests.post(self.domain + url, auth=self.basic_auth, data=payload, timeout=self.timeout)
                if r.status_code == 200:
                    return r.text
                else:
                    r.raise_for_status()
            except requests.RequestException as e:
                self.status_logger.warning("Retry number " + str(i) + " " + str(e) + " during request at url: "
                                           + str(self.domain + url))
                if i < self.n_retry-1:
                    time.sleep(self.retry_timeout)
                    continue
                else:
                    self.status_logger.error(str(e) + " during request at url: " + str(self.domain + url))
                    raise e

    def post_message(self, url, payload, timeout):
        """Use this function to send extracted data to OpenK)'s Ingestion APIs
                    """

        try:
            r = requests.post(url, data=payload, timeout=timeout)
            if r.status_code == 200:
                return
            else:
                r.raise_for_status()
        except requests.RequestException as e:
            self.status_logger.error(str(e) + " during request at url: " + str(url))
            raise e

    def extract(self):
        """Write here your extraction logic. In this case Liferay Json APIs are used to extract data about users, and
        send them to OpenK9 Ingestion"""

        try:
            payload = {
                "companyId": self.companyId
            }
            user_count = self.call_extraction_api("/api/jsonws/user/get-company-users-count", payload)
        except requests.RequestException:
            self.status_logger.error("No user count extracted. Extraction process aborted.")
            self.status = "ERROR"
            return

        self.status_logger.info(str(user_count) + " users founded")

        users_number = 0

        start_datetime = datetime.fromtimestamp(self.timestamp/1000)
        start_date = datetime.strftime(start_datetime, "%d-%b-%Y")

        self.status_logger.info("Getting users created from " + start_date)

        end_timestamp = datetime.utcnow().timestamp()*1000

        start = 0

        while start < int(user_count):

            end = start + 200

            payload = {
                "companyId": self.companyId,
                "start": start,
                "end": end
            }

            try:
                users_response = self.call_extraction_api('/api/jsonws/user/get-company-users', payload)
            except requests.RequestException:
                self.status_logger.error("Error during extraction of user from " + str(start) + " to " + str(end) +
                                         ". Extraction process aborted.")
                self.status = "ERROR"
                return

            user_list = json.loads(users_response)

            for user in user_list:

                start = start + 1

                self.status_logger.info("Extracting user " + str(start) + " of " + str(user_count))
                 
                try:
                    if user["modifiedDate"] > self.timestamp and user["status"] == 0:  # Filter using
                        # timestamp taken as input

                        contact_id = user["contactId"]

                        payload = {
                            "contactId": contact_id
                        }
                    
                        try:
                            user_response = self.call_extraction_api('/api/jsonws/contact/get-contact', payload)
                        except requests.RequestException:
                            self.status_logger.error("Error during extraction of informations about user. "
                                                     "Extraction process aborted.")
                            self.status = "ERROR"
                            return
                
                        user_info = json.loads(user_response)

                        # Building json to insert in datasourcePayload
                        user_values = {
                            "userId": user['userId'],
                            "screenName": user['screenName'],
                            "emailAddress": user_info['emailAddress'],
                            "employeeNumber": user_info['employeeNumber'],
                            "jobTitle": user_info['jobTitle'],
                            "jobClass": user_info['jobClass'],
                            "male": user_info['male'],
                            "twitterSn": user_info['twitterSn'],
                            "skypeSn": user_info['skypeSn'],
                            "facebookSn": user_info['facebookSn'],
                            "firstName": user_info['firstName'],
                            "middleName": user_info['middleName'],
                            "lastName": user_info['lastName'],
                            "fullName": user_info['firstName'] + " " + user_info['lastName'],
                            "birthday": user_info['birthday']
                        }

                        datasource_payload = {"user": user_values}

                        # Every message sent to Openk9 Ingestion must respect this structure
                        payload = {
                            "datasourceId": self.datasource_id,
                            "contentId": str(user['userId']),
                            "parsingDate": int(end_timestamp),
                            "rawContent": user_info['firstName'] + " " + user_info['lastName'],
                            "datasourcePayload": json.dumps(datasource_payload)
                        }

                        try:
                            self.post_message(self.ingestion_url, payload, 10)  # Post payload to OpenK9 Ingestion
                        except requests.RequestException:
                            self.status_logger.error("Problems during extraction of user with " + str(user['userId']))
                            self.status = "ERROR"
                            continue 
                        
                        users_number = users_number + 1
                except json.decoder.JSONDecodeError:
                    continue
            
        self.status_logger.info("Extraction ended")
        self.status_logger.info("Have been extracted " + str(users_number) + " users")
        return

    def join(self, timeout: Optional[float] = ...) -> str:
        threading.Thread.join(self)
        return self.status

    def run(self):

        try:
            self.extract()
        except KeyError as error:
            self.status = "ERROR"
            self.status_logger.error("Some problem with key " + str(error) + ". It could be a problem or with some "
                                                                             "config variables badly specified or with"
                                                                             " some key missing in train data file or "
                                                                             "in api response.")
            return

    def start(self) -> str:
        threading.Thread.start(self)
        return self.status
