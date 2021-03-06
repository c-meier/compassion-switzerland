# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2018 Compassion CH (http://www.compassion.ch)
#    @author: Emanuel Cino <ecino@compassion.ch>
#
#    The licence is in the file __manifest__.py
#
##############################################################################

from odoo import models, fields, tools, _

testing = tools.config.get('test_enable')


if not testing:
    # prevent these forms to be registered when running tests

    class GroupVisitPaymentForm(models.AbstractModel):
        _name = 'cms.form.event.group.visit.payment'
        _inherit = 'cms.form.payment'

        _payment_accept_redirect = '/event/payment/gpv_payment_validate'
        _display_type = 'full'

        event_id = fields.Many2one('crm.event.compassion')
        registration_id = fields.Many2one('event.registration')
        partner_name = fields.Char('Participant', readonly=True)
        amount = fields.Float(readonly=True)
        invoice_id = fields.Many2one('account.invoice')

        @property
        def _form_fieldsets(self):
            return [
                {
                    'id': 'payment',
                    'fields': [
                        'partner_name', 'amount', 'currency_id',
                        'acquirer_ids']
                },
            ]

        @property
        def form_title(self):
            if self.event_id:
                return self.event_id.name + ' ' + _("payment")
            else:
                return _("Travel payment")

        @property
        def submit_text(self):
            return _("Proceed with payment")

        @property
        def form_widgets(self):
            # Hide fields
            res = super(GroupVisitPaymentForm, self).form_widgets
            res['partner_name'] = 'cms_form_compassion.form.widget.readonly'
            res['amount'] = 'cms_form_compassion.form.widget.readonly'
            return res

        def form_init(self, request, main_object=None, **kw):
            form = super(GroupVisitPaymentForm, self).form_init(
                request, main_object, **kw)
            # Store ambassador and event in model to use it in properties
            registration = kw.get('registration')
            if registration:
                form.event_id = registration.compassion_event_id
                form.partner_id = registration.partner_id
                form.registration_id = registration
            return form

        def _form_load_partner_name(self, fname, field, value, **req_values):
            return self.partner_id.sudo().name

        def _form_load_amount(self, fname, field, value, **req_values):
            payment = self.registration_id.sudo().group_visit_invoice_id
            total_price = payment.amount_total
            tax = 1.0
            account = self.env['account.account'].sudo().search([
                ('code', '=', '4200')
            ])
            existing_tax = payment.invoice_line_ids.filtered(
                lambda l: l.account_id == account)
            if not existing_tax:
                tax = 1.019  # This is the tax for online payment
            return total_price * tax

        def form_before_create_or_update(self, values, extra_values):
            """ Inject invoice values """
            super(GroupVisitPaymentForm, self).form_before_create_or_update(
                values, extra_values)
            values['partner_id'] = self.partner_id.id

        def _form_create(self, values):
            # modifiy and add line
            group_visit_invoice = self.registration_id.sudo()\
                .group_visit_invoice_id
            # Admin
            analytic_account = self.env['account.analytic.account'].sudo()\
                .search([
                    ('code', '=', 'ATT_ADM')
                ])
            # Financial Expenses
            account = self.env['account.account'].sudo().search([
                ('code', '=', '4200')
            ])
            existing_tax = group_visit_invoice.invoice_line_ids.filtered(
                lambda l: l.account_id == account)

            if not existing_tax:
                group_visit_invoice.action_invoice_cancel()
                group_visit_invoice.action_invoice_draft()
                group_visit_invoice.write({
                    'invoice_line_ids': [(0, 0, {
                        'quantity': 1.0,
                        'price_unit': group_visit_invoice.amount_total * 0.019,
                        'account_id': account.id,
                        'name': 'Credit card tax',
                        'account_analytic_id': analytic_account.id,
                    })]
                })
                group_visit_invoice.action_invoice_open()

        def _edit_transaction_values(self, tx_values, form_vals):
            """ Add registration link and change reference. """
            tx_values.update({
                'invoice_id': self.registration_id.group_visit_invoice_id.id,
                'registration_id': self.registration_id.id,
                'reference': 'GROUP-VISIT-PAYMENT-' + str(
                    self.registration_id.id),
            })
