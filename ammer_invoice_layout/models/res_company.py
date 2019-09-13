# -*- coding: utf-8 -*-


from odoo import fields, models, api

class Company(models.Model):
    _inherit = 'res.company'

    report_background_image1 = fields.Binary('Background Image for Report Frontpage',
            help='Set Background Image for Report Frontpage')