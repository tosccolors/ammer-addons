from odoo import  api,fields, models,_
import requests
import json
from odoo.exceptions import ValidationError, UserError
from odoo.addons.queue_job.job import job


# Here is the class or new object for make connection between Odoo and WICS Server
# we have to used two values field in object.first one is auth_key to put the authentication key on your api and
# other one is secret_key to put the api Secret key values
# and then click on Connection Test button on view -- this button work on function action_request

class ResPartner(models.Model):
    _inherit = 'res.partner'

    house_no = fields.Integer('huisnummer')
    toegevoegd = fields.Char('Toegevoegd')


class ApiAuth(models.Model):
    _name='api.auth'
    
    auth_key = fields.Char('Authentication Key')
    secret_key = fields.Char('Secret Key')

    def action_request(self):
        # action_request function is send the request for wics server with your authentication and secret key
        # if api result is ok means success so raise message "Connection Successfuly" and if result is False so raise message
        # "Auth Key & Secret key is Wrong"

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

# here is shipment interval object
# Is it used for shipment interval means given shipment time interval(Hours)
# according to hours Check_shipment function is create a new queue job for pending orders on odoo server
#
class ShipTimeInterval(models.Model):
    _name = 'ship.time.interval'

    name =  fields.Integer(string="Shipment Check Interval (Hourly)")

# stock.immediate.transfer is odoo existing object its related to delivery order
# when user create a new order and confirm the delivery order this time work process method
# and we have to inherit this method and if odoo order is successfully valdate or confirm then call job_process method
# for create Odoo order in wics server
# and create order in wics server
class StockImmediateTransfer(models.TransientModel):
    _inherit = 'stock.immediate.transfer'

    @api.multi
    def process(self):
        # call super on process() method
        res = super(StockImmediateTransfer, self).process()
        if res:
            # its call the queue job method job_process() and pass picking id means order id in method parameters like "self.pick_id.id"
            order_id =self.with_delay().job_process(self.pick_id.id)
            # print ("order-id++++++++++", order_id, order_id.uuid)
            if order_id:
                jobid = self.env['queue.job'].search([('uuid','=', order_id.uuid)])
                if jobid:
                    self.pick_id.job_id = jobid.id
            # check shipment time interval (hours) in shipmentinterval table
            time_ids =  self.env['ship.time.interval'].search([('id','=',1)])
            for time in time_ids:
                hours = time.name
                # call the check_shipment() queue job method and pass picking id means order id in method parameters like "self.pick_id.id"
                shipment_id = self.with_delay(eta=60*60*hours).check_shipment(self.pick_id.id)
                # print("Shipment +++++++++", shipment_id)
                if shipment_id:
                    shipid = self.env['queue.job'].search([('uuid', '=', shipment_id.uuid)])
                    if shipid:
                        self.pick_id.shipment_job_id = shipid.id

    # job_process() job method is define and get active_id of odoo order
    @job()
    @api.multi
    def job_process(self, active_id):
        if active_id:
            #here is it search the active id order on stock.picking delivery order object
            picking_ids =  self.env['stock.picking'].search([('id','=',active_id)])
            #here is it get the api authentication values using of search
            auth_ids =  self.env['api.auth'].search([('id','=',1)])
            for key in auth_ids:
                username = key.auth_key #'BdZbnhPKXQTzbiOPKuPv'
                password = key.secret_key #'HzCyjESQKNWvQkjEwVqR'
                auth = (username, password)
                headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
                # send request of wics server with api authentications
                result = requests.get('http://test.servicelayer.wics.nl/api/login', auth=auth, headers=headers)
                if result.ok:
                    child = []
                    item_dict = {}
                    # here is it create a order dict for wics server order
                    for lines in picking_ids.move_lines:
                        item_dict['itemCode'] = lines.product_id.default_code
                        item_dict['itemDescription'] = lines.product_id.name
                        item_dict['quantity'] = lines.product_uom_qty
                        item_dict['variantCode'] = '500'
                        child.append(dict(item_dict))
                    task = {
                        "reference": picking_ids.origin or " ",
                        "additionalReference": picking_ids.name ,
                        "deliveryDate": picking_ids.min_date,
                        "webshopId": 1,
                        "note": picking_ids.note or " ",
                        "rembours": 12.5,
                        "tag": "Afhalen in Werkendam",
                        "invoiceAddress": {
                            "name": picking_ids.partner_id.name,
                            "nameExtension": " ",
                            "company": "WICS",
                            "street": picking_ids.partner_id.street or " ",
                            "streetNumber": picking_ids.partner_id.house_no or " ",
                            "extension": picking_ids.partner_id.toegevoegd or " ",
                            "secondAddressLine": picking_ids.partner_id.street2 or " ",
                            "thirdAddressLine": " ",
                            "zipcode": picking_ids.partner_id.zip or " " ,
                            "city": picking_ids.partner_id.city or " ",
                            "state": picking_ids.partner_id.state_id.name or " ",
                            "country": picking_ids.partner_id.country_id.code or " ",#'IN',
                            "phoneNumber": picking_ids.partner_id.phone,
                            "mobileNumber": picking_ids.partner_id.mobile,
                            "email": picking_ids.partner_id.email,
                            "language": picking_ids.partner_id.lang
                        },
                        "deliveryAddress": {
                            "name": picking_ids.partner_id.name,
                            "nameExtension": " ",
                            "company": "WICS",
                            "street": picking_ids.partner_id.street or " ",
                            "streetNumber": picking_ids.partner_id.house_no or " ",
                            "extension": picking_ids.partner_id.toegevoegd or " ",
                            "secondAddressLine": picking_ids.partner_id.street2 or " ",
                            "thirdAddressLine": " ",
                            "zipcode": picking_ids.partner_id.zip or " ",
                            "city": picking_ids.partner_id.city or " ",
                            "state": picking_ids.partner_id.state_id.name or " ",
                            "country": picking_ids.partner_id.country_id.code or " ",
                            "phoneNumber": picking_ids.partner_id.phone,
                            "mobileNumber": picking_ids.partner_id.mobile,
                            "email": picking_ids.partner_id.email,
                            "language": picking_ids.partner_id.lang
                        },
                        "lines": child
                    }
                    # created dictionary using of post method create order on wics server and order is created on wics server
                    resp = requests.post('http://test.servicelayer.wics.nl/api/order', auth=auth, json=task,
                                         headers=headers)
                    if resp.ok:
                        # then if data is none so create a new queue job for this order in odoo server
                        resp = json.loads(resp.text)
                        if resp['success']== False:
                            picking_ids.order_status = 'failure'
                        else:
                            picking_ids.order_status = 'success'



    # here is check_shipment() queue job method for check order shipments
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
                # send request on wics server with api authentication
                result = requests.get('http://test.servicelayer.wics.nl/api/login', auth=auth, headers=headers)
                if result.ok:
                    # if result is ok or success
                    wics = picking_ids.origin
                    url = "http://test.servicelayer.wics.nl/api/shipment/%s" % (wics)
                    # then again send request for wics server shipments and get the success
                    resp_get = requests.get(url, auth=auth, headers=headers)
                    if resp_get.ok:
                        # then if data is none so create a new queue job for this order in odoo server
                        resp = json.loads(resp_get.text)
                        if resp['success'] == False:
                            time_ids = self.env['ship.time.interval'].search([('id', '=', 1)])
                            for time in time_ids:
                                hours = time.name
                                shipment_id = self.with_delay(eta=60 * 60 * hours).check_shipment(picking_ids.id)
                                if shipment_id:
                                    shipid = self.env['queue.job'].search([('uuid', '=', shipment_id.uuid)])
                                    if shipid:
                                        picking_ids.shipment_job_id = shipid.id
                        else:
                            # and if get data not none then get "traceandtrace" and "traceandtraceurl" and change odoo delivery order status on "shipped"
                            picking_ids.state = 'shipped'
                            if resp['data'] != None:
                                for res in resp['data']:
                                    picking_ids.trace_and_trace = res['trackAndTrace']
                                    picking_ids.trace_and_url = res['trackAndTraceUrl']
        return True


# inherit odoo existing stock.picking object and traceandtrace and traceandtraceurl values in odoo order form
class StockIPicking(models.Model):
    _inherit = 'stock.picking'

    trace_and_trace = fields.Char(string="Trace and Trace")
    trace_and_url = fields.Char(string="Trace and Trace Url")
    state = fields.Selection(selection_add=[('shipped', 'Shipped')])
    order_status = fields.Selection([('success', 'WICS accepted'), ('failure', 'WICS rejected')], string='Status')
    job_id = fields.Many2one('queue.job', string='Order Job', )
    shipment_job_id = fields.Many2one('queue.job', string='Shipment Tracking')
    issue = fields.Text(string='Issue')

    @api.multi
    def create_order_job(self):
            # its call the queue job method order_job_process() and pass picking id means order id in method parameters like "self.id"
            order_id = self.with_delay().order_job_process(self.id)
            if order_id:
                jobid = self.env['queue.job'].search([('uuid', '=', order_id.uuid)])
                if jobid:
                    self.job_id = jobid.id

    @job()
    @api.multi
    def order_job_process(self, active_id):
        if active_id:
            # here is it search the active id order on stock.picking delivery order object
            picking_ids = self.env['stock.picking'].search([('id', '=', active_id)])
            # here is it get the api authentication values using of search
            auth_ids = self.env['api.auth'].search([('id', '=', 1)])
            for key in auth_ids:
                username = key.auth_key  # 'BdZbnhPKXQTzbiOPKuPv'
                password = key.secret_key  # 'HzCyjESQKNWvQkjEwVqR'
                auth = (username, password)
                headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
                # send request of wics server with api authentications
                result = requests.get('http://test.servicelayer.wics.nl/api/login', auth=auth, headers=headers)
                if result.ok:
                    child = []
                    item_dict = {}
                    # here is it create a order dict for wics server order
                    for lines in picking_ids.move_lines:
                        item_dict['itemCode'] = lines.product_id.default_code
                        item_dict['itemDescription'] = lines.product_id.name
                        item_dict['quantity'] = lines.product_uom_qty
                        item_dict['variantCode'] = '500'
                        child.append(dict(item_dict))
                    task = {
                        "reference": picking_ids.origin or " ",
                        "additionalReference": picking_ids.name,
                        "deliveryDate": picking_ids.min_date,
                        "webshopId": 1,
                        "note": picking_ids.note or " ",
                        "rembours": 12.5,
                        "tag": "Afhalen in Werkendam",
                        "invoiceAddress": {
                            "name": picking_ids.partner_id.name,
                            "nameExtension": " ",
                            "company": "WICS",
                            "street": picking_ids.partner_id.street or " ",
                            "streetNumber": picking_ids.partner_id.house_no or " ",
                            "extension": picking_ids.partner_id.toegevoegd or " ",
                            "secondAddressLine": picking_ids.partner_id.street2 or " ",
                            "thirdAddressLine": " ",
                            "zipcode": picking_ids.partner_id.zip or " ",
                            "city": picking_ids.partner_id.city or " ",
                            "state": picking_ids.partner_id.state_id.name or " ",
                            "country": picking_ids.partner_id.country_id.code or " ",  # 'IN',
                            "phoneNumber": picking_ids.partner_id.phone,
                            "mobileNumber": picking_ids.partner_id.mobile,
                            "email": picking_ids.partner_id.email,
                            "language": picking_ids.partner_id.lang
                        },
                        "deliveryAddress": {
                            "name": picking_ids.partner_id.name,
                            "nameExtension": " ",
                            "company": "WICS",
                            "street": picking_ids.partner_id.street or " ",
                            "streetNumber": picking_ids.partner_id.house_no or " ",
                            "extension": picking_ids.partner_id.toegevoegd or " ",
                            "secondAddressLine": picking_ids.partner_id.street2 or " ",
                            "thirdAddressLine": " ",
                            "zipcode": picking_ids.partner_id.zip or " ",
                            "city": picking_ids.partner_id.city or " ",
                            "state": picking_ids.partner_id.state_id.name or " ",
                            "country": picking_ids.partner_id.country_id.code or " ",
                            "phoneNumber": picking_ids.partner_id.phone,
                            "mobileNumber": picking_ids.partner_id.mobile,
                            "email": picking_ids.partner_id.email,
                            "language": picking_ids.partner_id.lang
                        },
                        "lines": child
                    }
                    # created dictionary using of post method create order on wics server and order is created on wics server
                    resp = requests.post('http://test.servicelayer.wics.nl/api/order', auth=auth, json=task,
                                         headers=headers)
                    if resp.ok:
                        # then if data is none so create a new queue job for this order in odoo server
                        resp = json.loads(resp.text)
                        if resp['success'] == False:
                            picking_ids.order_status = 'failure'
                            picking_ids.issue = resp['message']
                        else:
                            picking_ids.order_status = 'success'

    