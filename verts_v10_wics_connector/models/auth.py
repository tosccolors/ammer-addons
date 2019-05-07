from odoo import  api,fields, models,_
import requests
import json
from odoo.exceptions import ValidationError, UserError
from odoo.addons.queue_job.job import job


class ApiAuth(models.Model):
    _name='api.auth'
    
    auth_key = fields.Char('Authentication Key')
    secret_key = fields.Char('Secret Key')

    def action_request(self):
        username = self.auth_key #'BdZbnhPKXQTzbiOPKuPv'
        password = self.secret_key #'HzCyjESQKNWvQkjEwVqR'
        auth = (username, password)
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        result = requests.get('http://test.servicelayer.wics.nl/api/login', auth=auth, headers=headers)
        if result.ok:
            raise UserError(_("Connection Successfully"))
        else:
            raise UserError(_("Auth Key & Secret key is Wrong"))
        return True


class ShipTimeInterval(models.Model):
    _name = 'ship.time.interval'

    name =  fields.Integer(string="Shipment Check Interval (Hourly)")


class StockImmediateTransfer(models.TransientModel):
    _inherit = 'stock.immediate.transfer'

    @api.multi
    def process(self):
        res = super(StockImmediateTransfer, self).process()
        if res:
            self.with_delay().job_process(self.pick_id.id)
            time_ids =  self.env['ship.time.interval'].search([('id','=',1)])
            for time in time_ids:
                hours = time.name
                self.with_delay(eta=60*60*hours).check_shipment(self.pick_id.id)

    @job()
    @api.multi
    def job_process(self, active_id):
        if active_id:
            picking_ids =  self.env['stock.picking'].search([('id','=',active_id)])
            auth_ids =  self.env['api.auth'].search([('id','=',1)])
            for key in auth_ids:
                username = key.auth_key #'BdZbnhPKXQTzbiOPKuPv'
                password = key.secret_key #'HzCyjESQKNWvQkjEwVqR'
                auth = (username, password)
                headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
                result = requests.get('http://test.servicelayer.wics.nl/api/login', auth=auth, headers=headers)
                if result.ok:
                    child = []
                    item_dict = {}
                    for lines in picking_ids.move_lines:
                        item_dict['itemCode'] = lines.product_id.default_code
                        item_dict['itemDescription'] = lines.product_id.name
                        item_dict['quantity'] = lines.product_uom_qty
                        item_dict['variantCode'] = '500'
                        child.append(dict(item_dict))
                    task = {
                        "reference": picking_ids.name,
                        "additionalReference": picking_ids.origin,
                        "deliveryDate": picking_ids.min_date,
                        "webshopId": 1,
                        "note": picking_ids.note,
                        "rembours": 12.5,
                        "tag": "Afhalen in Werkendam",
                        "invoiceAddress": {
                            "name": picking_ids.partner_id.name,
                            "nameExtension": "",
                            "company": "WICS",
                            "street": picking_ids.partner_id.street,
                            "streetNumber": 32,
                            "extension": "B",
                            "secondAddressLine": picking_ids.partner_id.street2,
                            "thirdAddressLine": "",
                            "zipcode": picking_ids.partner_id.zip,
                            "city": picking_ids.partner_id.city,
                            "state": picking_ids.partner_id.state_id.name,
                            "country": picking_ids.partner_id.country_id.code,#'IN',
                            "phoneNumber": picking_ids.partner_id.phone,
                            "mobileNumber": picking_ids.partner_id.mobile,
                            "email": picking_ids.partner_id.email,
                            "language": picking_ids.partner_id.lang
                        },
                        "deliveryAddress": {
                            "name": picking_ids.partner_id.name,
                            "nameExtension": "",
                            "company": "WICS",
                            "street": picking_ids.partner_id.street,
                            "streetNumber": 32,
                            "extension": "B",
                            "secondAddressLine": picking_ids.partner_id.street2,
                            "thirdAddressLine": "",
                            "zipcode": picking_ids.partner_id.zip,
                            "city": picking_ids.partner_id.city,
                            "state": picking_ids.partner_id.state_id.name,
                            "country": picking_ids.partner_id.country_id.code,
                            "phoneNumber": picking_ids.partner_id.phone,
                            "mobileNumber": picking_ids.partner_id.mobile,
                            "email": picking_ids.partner_id.email,
                            "language": picking_ids.partner_id.lang
                        },
                        "lines": child
                    }
                    resp = requests.post('http://test.servicelayer.wics.nl/api/order', auth=auth, json=task,
                                         headers=headers)
                    # print("resp create+++", resp.status_code)

    @job()
    @api.multi
    def check_shipment(self, active_id):
        if active_id:
            picking_ids =  self.env['stock.picking'].search([('id','=',active_id)])
            auth_ids = self.env['api.auth'].search([('id', '=', 1)])
            for key in auth_ids:
                username = key.auth_key  # 'BdZbnhPKXQTzbiOPKuPv'
                password = key.secret_key  # 'HzCyjESQKNWvQkjEwVqR'
                auth = (username, password)
                headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
                result = requests.get('http://test.servicelayer.wics.nl/api/login', auth=auth, headers=headers)
                if result.ok:
                    wics = picking_ids.name
                    url = "http://test.servicelayer.wics.nl/api/shipment/%s" % (wics)
                    resp_get = requests.get(url, auth=auth, headers=headers)
                    if resp_get.ok:
                        resp = json.loads(resp_get.text)
                        if resp['data'] == None:
                            time_ids = self.env['ship.time.interval'].search([('id', '=', 1)])
                            for time in time_ids:
                                hours = time.name
                                self.with_delay(eta=60 * 60 * hours).check_shipment(picking_ids.id)
                        else:
                            for res in resp['data']:
                                picking_ids.state = 'shipped'
                                picking_ids.trace_and_trace = res['trackAndTrace']
                                picking_ids.trace_and_url = res['trackAndTraceUrl']
        return True


class StockIPicking(models.Model):
    _inherit = 'stock.picking'

    trace_and_trace = fields.Char(string="Trace and Trace")
    trace_and_url = fields.Char(string="Trace and Trace Url")
    state = fields.Selection(selection_add=[('shipped', 'Shipped')])

    # def action_request2(self):
    #     auth_ids = self.env['api.auth'].search([('id', '=', 1)])
    #     for key in auth_ids:
    #         username = key.auth_key  # 'BdZbnhPKXQTzbiOPKuPv'
    #         password = key.secret_key  # 'HzCyjESQKNWvQkjEwVqR'
    #         auth = (username, password)
    #         headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    #         result = requests.get('http://test.servicelayer.wics.nl/api/login', auth=auth, headers=headers)
    #         # print("result ++++++++++++", result, result.status_code)
    #         if result.ok:
    #             wics = self.name
    #             url = "http://test.servicelayer.wics.nl/api/shipment/%s" % (wics)
    #             resp_get = requests.get(url, auth=auth, headers=headers)
    #             print('for order shipment:', resp_get)
    #             if resp_get.ok:
    #                 resp = json.loads(resp_get.text)
    #                 print('for:', resp)
    #                 if resp['data'] == None:
    #                     print ("data None")
    #                     # time_ids = self.env['ship.time.interval'].search([('id', '=', 1)])
    #                     # for time in time_ids:
    #                     #     hours = time.name
    #                     #     self.with_delay(eta=60 * 60 * hours).check_shipment(picking_ids.id)
    #                 else:
    #                     print("else")
    #                     for res in resp['data']:
    #                         self.state = 'shipped'
    #                         self.trace_and_trace = res['trackAndTrace']
    #                         self.trace_and_url = res['trackAndTraceUrl']
    #     return True
