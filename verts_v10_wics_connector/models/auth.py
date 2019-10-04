import logging
from odoo import models, fields, api, _
import requests
import json
from odoo.exceptions import ValidationError, UserError
from odoo.addons.queue_job.job import job
import logging
_logger = logging.getLogger(__name__)

# Here is the class or new object for make connection between Odoo and WICS Server
# we have to used two values field in object.first one is auth_key to put the authentication key on your api and
# other one is secret_key to put the api Secret key values
# and then click on Connection Test button on view -- this button work on function action_request

class ResPartner(models.Model):
    _inherit = 'res.partner'

    house_no = fields.Integer('huisnummer')
    toegevoegd = fields.Char('Toegevoegd')


class WicsApiAuth(models.Model):
    _name='wics.api.auth'
    _description = 'Wics API config interface'
    endpoint = fields.Char(string='Endpoint',
                           help="Protocol, domain and method, e.g. http://test.servicelayer.wics.nl/api/login")
    auth_key = fields.Char('Authentication Key')
    secret_key = fields.Char('Secret Key')


    # show only first record to configure, no options to create an additional one
    @api.multi
    def default_view(self):
        configurations = self.search([])
        if not configurations:
            endpoint = "http://test.servicelayer.wics.nl/api/login"
            self.write({'endpoint': endpoint})
            configuration = self.id
            _logger.info("Wics order interface configuration record created")
        else:
            configuration = configurations[0].id
        action = {
            "type": "ir.actions.act_window",
            "res_model": "wics.api.auth",
            "view_type": "form",
            "view_mode": "form",
            "res_id": configuration,
            "target": "inline",
        }
        return action

    def wics_action_request(self):
        # action_request function is send the request for wics server with your authentication and secret key
        # if api result is ok means success so raise message "Connection Successfuly" and if result is False so raise message
        # "Auth Key & Secret key is Wrong"

        username = self.auth_key #'BdZbnhPKXQTzbiOPKuPv'
        password = self.secret_key #'HzCyjESQKNWvQkjEwVqR'
        auth = (username, password)
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        result = requests.get(self.endpoint, auth=auth, headers=headers)
        if result.ok:
            raise UserError(_("Connection Successfull"))
        else:
            raise UserError(_("Auth Key and/or Secret key is Wrong"))
        return True

    @api.multi
    def save_config(self):
        self.write({})
        return True


# inherit odoo existing stock.picking object and traceandtrace and traceandtraceurl values in odoo order form
class StockIPicking(models.Model):
    _inherit = 'stock.picking'

    trace_and_trace = fields.Char(string="Trace and Trace")
    trace_and_url = fields.Char(string="Trace and Trace Url")
    wics_status = fields.Selection([('success', 'WICS accepted'),
                                    ('failure', 'WICS rejected'),
                                    ('shipped', 'WICS shipped')],
                                    string='Status')
    job_id = fields.Many2one('queue.job', string='Order Job', )
    issue = fields.Text(string='Issue')

    @api.multi
    def do_transfer(self):
        """ If no pack operation, we do simple action_done of the picking.
        Otherwise, do the pack operations. """
        super(StockIPicking, self.with_context(wics=True)).do_transfer()

    @api.multi
    def action_done(self):
        """Inherited:Changes picking state to done by processing the Stock Moves of the Picking
        Normally that happens when the button "Done" is pressed on a Picking view.
        Here it is called to initiate the WICS call
        @return: True
        """
        wics = self.env.context.get('wics')
        _logger.info("\n\n\n")
        _logger.info("self= %s, wics= %s" % (self, wics))
        _logger.info("\n\n\n")
        import pdb; pdb.set_trace()
        if wics:
            pickings = self.filtered(lambda s: s.state in ['draft', 'assigned', 'confirmed'])
            _logger.info("\n\n\n")
            _logger.info("pickings= %s, state= %s" % (pickings, wics))
            _logger.info("\n\n\n")
            for picking in pickings:
                if picking.job_id and picking.job_id.state not in ['done','failed']:
                    raise UserError(_("Job Queue is still running for this picking: %s"), picking.name)
                delayed_job = picking.with_delay(description=picking.name).wics_order_process()
                picking.job_id = delayed_job.id
        return super(StockIPicking, self).action_done()

    @job()
    @api.multi
    def wics_order_process(self):
        self.ensure_one()
        # here is it get the api authentication values using of search
        config = self.env['wics.api.auth'].search([])[0]
        if not config:
            return "No Wics order interface configuration record found"
        if not config.endpoint or not config.auth_key or not config.secret_key:
            return "Incomplete Wics order interface configuration. Need input on endpoint, auth_key and " \
                   "secret_key. "

        username = config.auth_key  # 'BdZbnhPKXQTzbiOPKuPv'
        password = config.secret_key  # 'HzCyjESQKNWvQkjEwVqR'
        auth = (username, password)
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        # send request of wics server with api authentications
        result = requests.get(config.endpoint, auth=auth, headers=headers)
        if result.ok:
            child = []
            item_dict = {}
            # here we create an order dict for wics server
            for lines in self.move_lines:
                item_dict['itemCode'] = lines.product_id.default_code
                item_dict['itemDescription'] = lines.product_id.name
                item_dict['quantity'] = lines.product_uom_qty
                item_dict['variantCode'] = '500'
                child.append(dict(item_dict))
            task = {
                "reference": self.origin or " ",
                "additionalReference": self.name,
                "deliveryDate": self.min_date,
                "webshopId": 1,
                "note": self.note or " ",
                "rembours": 12.5,
                "tag": "Afhalen in Werkendam",
                "invoiceAddress": {
                    "name": self.partner_id.name,
                    "nameExtension": " ",
                    "company": "WICS",
                    "street": self.partner_id.street or " ",
                    "streetNumber": self.partner_id.house_no or " ",
                    "extension": self.partner_id.toegevoegd or " ",
                    "secondAddressLine": self.partner_id.street2 or " ",
                    "thirdAddressLine": " ",
                    "zipcode": self.partner_id.zip or " ",
                    "city": self.partner_id.city or " ",
                    "state": self.partner_id.state_id.name or " ",
                    "country": self.partner_id.country_id.code or " ",  # 'IN',
                    "phoneNumber": self.partner_id.phone,
                    "mobileNumber": self.partner_id.mobile,
                    "email": self.partner_id.email,
                    "language": self.partner_id.lang
                },
                "deliveryAddress": {
                    "name": self.partner_id.name,
                    "nameExtension": " ",
                    "company": "WICS",
                    "street": self.partner_id.street or " ",
                    "streetNumber": self.partner_id.house_no or " ",
                    "extension": self.partner_id.toegevoegd or " ",
                    "secondAddressLine": self.partner_id.street2 or " ",
                    "thirdAddressLine": " ",
                    "zipcode": self.partner_id.zip or " ",
                    "city": self.partner_id.city or " ",
                    "state": self.partner_id.state_id.name or " ",
                    "country": self.partner_id.country_id.code or " ",
                    "phoneNumber": self.partner_id.phone,
                    "mobileNumber": self.partner_id.mobile,
                    "email": self.partner_id.email,
                    "language": self.partner_id.lang
                },
                "lines": child
            }
            # created dictionary using of post method create order on wics server and order is created on wics server
            resp = requests.post(config.endpoint, auth=auth, json=task,
                                 headers=headers)
            if resp.ok:
                # if data is none or failure message
                resp = json.loads(resp.text)
                if resp['success'] == False:
                    self.wics_status = 'failure'
                    self.issue = resp['message']
                else:
                    self.wics_status = 'success'
                    self.with_context(wics=False).action_done()

    # here is check_shipment() cron job method for check order shipments,
    # configurable in cron, default once every hour
    @api.multi
    def check_shipment(self):
        picking_ids = self.search([('wics_status', '=', 'success')])
        if not picking_ids:
            return
        config = self.env['wics.api.auth'].search([])[0]
        if not config:
            return "No Wics order interface configuration record found"
        if not config.endpoint or not config.auth_key or not config.secret_key:
            return "Incomplete Wics order interface configuration. Need input on endpoint, auth_key and " \
                   "secret_key. "

        username = config.auth_key  # 'BdZbnhPKXQTzbiOPKuPv'
        password = config.secret_key  # 'HzCyjESQKNWvQkjEwVqR'
        auth = (username, password)
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        # send request on wics server with api authentication
        result = requests.get(config.endpoint, auth=auth, headers=headers)
        if result.ok:
            for picking in picking_ids:
                wics = picking.origin
                url = "http://test.servicelayer.wics.nl/api/shipment/%s" % (wics)
                # then again send request for wics server shipments and get the success
                resp_get = requests.get(url, auth=auth, headers=headers)
                if resp_get.ok:
                    resp = json.loads(resp_get.text)
                    # and if get data not none then get "traceandtrace" and "traceandtraceurl" and change odoo delivery order status on "shipped"
                    picking.state = 'shipped'
                    if resp['data'] != None:
                        for res in resp['data']:
                            picking.trace_and_trace = res['trackAndTrace']
                            picking.trace_and_url = res['trackAndTraceUrl']
        return


    