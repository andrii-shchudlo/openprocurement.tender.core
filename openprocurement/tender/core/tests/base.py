# -*- coding: utf-8 -*-
import os
from copy import deepcopy
from datetime import datetime, timedelta
from uuid import uuid4
from requests.models import Response
from base64 import b64encode
from urllib import urlencode

from openprocurement.api.utils import SESSION, apply_data_patch
from openprocurement.api.tests.base import BaseWebTest


now = datetime.now()


class BaseTenderWebTest(BaseWebTest):
    initial_data = None
    initial_status = None
    initial_bids = None
    initial_lots = None
    docservice = False
    relative_to = os.path.dirname(__file__)

    def set_status(self, status, extra=None):
        if extra:
            data.update(extra)

        tender = self.db.get(self.tender_id)
        tender.update(apply_data_patch(tender, data))
        self.db.save(tender)

        authorization = self.app.authorization
        self.app.authorization = ('Basic', ('chronograph', ''))
        #response = self.app.patch_json('/tenders/{}'.format(self.tender_id), {'data': {'id': self.tender_id}})
        response = self.app.get('/tenders/{}'.format(self.tender_id))
        self.app.authorization = authorization
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(response.content_type, 'application/json')
        return response

    def setUp(self):
        super(BaseTenderWebTest, self).setUp()
        self.create_tender()
        if self.docservice:
            self.setUpDS()

    def setUpDS(self):
        self.app.app.registry.docservice_url = 'http://localhost'
        test = self
        def request(method, url, **kwargs):
            response = Response()
            if method == 'POST' and '/upload' in url:
                url = test.generate_docservice_url()
                response.status_code = 200
                response.encoding = 'application/json'
                response._content = '{{"data":{{"url":"{url}","hash":"md5:{md5}","format":"application/msword","title":"name.doc"}},"get_url":"{url}"}}'.format(url=url, md5='0'*32)
                response.reason = '200 OK'
            return response

        self._srequest = SESSION.request
        SESSION.request = request

    def setUpBadDS(self):
        self.app.app.registry.docservice_url = 'http://localhost'
        def request(method, url, **kwargs):
            response = Response()
            response.status_code = 403
            response.encoding = 'application/json'
            response._content = '"Unauthorized: upload_view failed permission check"'
            response.reason = '403 Forbidden'
            return response

        self._srequest = SESSION.request
        SESSION.request = request

    def generate_docservice_url(self):
        uuid = uuid4().hex
        key = self.app.app.registry.docservice_key
        keyid = key.hex_vk()[:8]
        signature = b64encode(key.signature("{}\0{}".format(uuid, '0' * 32)))
        query = {'Signature': signature, 'KeyID': keyid}
        return "http://localhost/get/{}?{}".format(uuid, urlencode(query))

    def create_tender(self):
        data = deepcopy(self.initial_data)
        response = self.app.post_json('/tenders', {'data': data})
        tender = response.json['data']
        self.tender_token = response.json['access']['token']
        self.tender_id = tender['id']
        if self.initial_status != tender['status']:
            self.set_status(self.initial_status)

    def tearDownDS(self):
        SESSION.request = self._srequest

    def tearDown(self):
        if self.docservice:
            self.tearDownDS()
        del self.db[self.tender_id]
        super(BaseTenderWebTest, self).tearDown()