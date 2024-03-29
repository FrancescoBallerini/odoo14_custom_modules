import logging
import traceback

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ProductPricelistItem(models.Model):
    _inherit = "product.pricelist.item"

    @api.depends("product_tmpl_id.seller_ids", "product_id.seller_ids")
    def _compute_product_pricelist_selling_price(self):
        # add seller_ids to dependencies to recompute the
        # selling price in case fields have store=True
        return super()._compute_product_pricelist_selling_price()

    def _set_product_pricelist_selling_price(self, product_price, product):
        if self.base == "supplierinfo":
            # no need to call _compute_price(), actually it would show
            # inconsistent outcome because price would be computed twice
            self.product_pricelist_selling_price = product_price

            # compute taxed selling price amount. In the context of
            # a pricelist, as a convention we take the first tax
            # linked to the product
            def_tax_id = product.taxes_id[0] if product.taxes_id else None
            taxed_amount = 0.00
            if def_tax_id:
                taxed_amount = def_tax_id._compute_amount(
                    base_amount=self.product_pricelist_selling_price,
                    price_unit=self.product_pricelist_selling_price,
                    quantity=1.0,
                    product=product,
                )

            self.product_pricelist_selling_price_taxed = (
                self.product_pricelist_selling_price + taxed_amount
            )

        else:
            return super()._set_product_pricelist_selling_price(
                product_price=product_price, product=product
            )

    @api.model
    def _get_allowed_base_rule(self):

        """Add supplierinfo key. This method is here to avoid
        key errors in price_compute() call on main compute method.
        Only allowed key will re-trigger price recomputation."""

        return super()._get_allowed_base_rule() + ["supplierinfo"]

    def _get_product_price_rule_base(self, product):
        """
        Inheritable method to compute and return selling
        price, depending on 'based on' parameter.
        Depending on 'base' we might want to use another
        method, change context, use different args...

        @Override: return product price in the context
        of a pricelist-rule based on supplierinfo price
        after pricelist rule is applied. Keeps User
        Interface responsive for @api.depends.

        :param product: product linked to pricelist-rule

        :returns:
        - product price (computed by rule parameters)
        - 0.00 if not able to compute
        """

        product_price = super()._get_product_price_rule_base(product=product)

        if self.compute_price == "formula" and self.base == "supplierinfo":

            if product._name == "product.template":
                # better to check for product.product_variant_id. In theory every
                # product should have a dummy variant, but in some cases (e.g. when
                # product is archived) it will not be able to retrieve it
                if not product.product_variant_ids[:1]:
                    # todo put this visible in form as well
                    _logger.warning(
                        "Not able to retrieve variant IDS for %s. "
                        "Hint: this might happen while product is archived. " % product
                    )
                    # compute to `True`: show alert div on form
                    self.unable_to_retrieve_variant = True
                    # skip computation: return dummy price
                    return 0.00

                product = product.product_variant_ids[:1]

            # We prefer the usage of _compute_price() over _compute_price_rule()
            # (or other method that will be called on ProductPricelist) because
            # it's the only way to have responsive UI (otherwise UI will update
            # only when the whole product record get saved).
            # We must use lower level approach at this point, because if we call
            # _get_supplierinfo_pricelist_price, the price returned will already
            # have pricelist-rule applied and result will be inconsistent. In
            # order to provide a responsive UI and give consistent results we
            # have to call _select_seller into _compute_price

            seller_price = self._fetch_supplierinfo_price(product=product)

            # _compute_price(): UI responsive on @api.depends
            product_price = self._compute_price(
                price=seller_price,
                price_uom=product.uom_id,
                product=product,
                quantity=self.min_quantity,
                partner=self.filter_supplier_id,
            )

        return product_price

    def _get_percent_change_rule_base(self, product):

        """@override: compute discount percentage based on user
        input and computed selling price, for pricelists based
        on supplierinfo prices

         :returns dictionary 'discount' with two keys:

        * 'discount_field_name': the field on which percent change applies
        (can be 'price_discount' or 'percent_price')

        * 'discount': percentage change computed by formula:

         ``(input - computed selling price) / computed selling price x 100``
        """

        discount = super()._get_percent_change_rule_base(product=product)

        if self.compute_price == "formula" and self.base == "supplierinfo":

            if product._name == "product.template":
                # better to check for product.product_variant_id. In theory every
                # product should have a dummy variant, but in some cases (e.g. when
                # product is archived) it will not be able to retrieve it
                if not product.product_variant_ids[:1]:
                    # compute to `True`: show alert div on form
                    self.unable_to_retrieve_variant = True
                    # Compute a specific error message to be shown in this case:
                    # otherwise if we just pass a dummy value of 0.00 it would
                    # only trigger a generic ZeroDivisionError exception in the
                    # error handler `_manage_percent_change_user_input_errors()`
                    discount["error"] = (
                        "Not able to retrieve variant IDS for %s. "
                        "Hint: this might happen while product is archived. " % product
                    )
                    return discount

                product = product.product_variant_ids[:1]

            # _compute_price() is the only UI responsive method for @api.depends,
            # so we must go low level, see _get_product_price_rule_base for info

            seller_price = self._fetch_supplierinfo_price(product=product)

            discount["discount_field_name"] = "price_discount"
            discount["product_price"] = seller_price

        return discount

    def set_percentage_change(self):

        """Inheritable method: make checks before the assignement
        of % discount or change fetch for the price based on rule setup"""

        if self.base == "supplierinfo":
            discount_dict = self._get_percentage_change()
            self._manage_percent_change_user_input_errors(discount_dict)
            # no user input error on input field, try to set the % field
            price = discount_dict.get("product_price")

            try:
                discount = ((price - self.percent_change_user_input) / price) * 100
            except ZeroDivisionError:
                raise UserError(
                    _(
                        "Supplier provided purchase price is equal to 0.00.\n"
                        "Cannot divide by zero, please correct parameters and try again.\n\n%s"
                        "Hint: if provided values are correct try to save unsaved records and "
                        "try again." % (traceback.format_exc())
                    )
                )
            discount_field_name = discount_dict.get("discount_field_name")
            if discount_field_name and discount:
                self[discount_field_name] = discount
            # reset input value, after correct execution
            self._reset_percent_change_user_input()
            return
        return super().set_percentage_change()

    def _fetch_supplierinfo_price(self, product):

        """Low level method: call _select_seller and return
         a specific seller price before the pricelist-rule
         is applied on it.

        :param product: product in the context of a pricelist
        rule that has to be searched on in order to fetch the
        proper requested related seller prices

        :return float: seller price before rule computation
        """

        seller_id = product.with_context(
            override_min_qty=self.no_supplierinfo_min_quantity,
        )._select_seller(
            partner_id=self.filter_supplier_id, quantity=self.min_quantity, date=None
        )

        if not seller_id:
            return 0.0

        # override to fetch different prices from seller (custom fields..)
        price_type = seller_id._get_supplierinfo_price_type()

        # We got the proper seller, but we can't use price_compute()
        # to retrieve the 'vanilla' supplierinfo price since it would
        # return a dummy price of 1.0. This means that we have to
        # explicitly deal with currency rate (again) in case seller
        # currency is different.

        pricelist_currency = self.currency_id or self.pricelist_id.currency_id
        company = self.env.company

        seller_price = seller_id._get_seller_price(
            price_type=price_type,
            currency=pricelist_currency,
            uom=False,
            company=company,
        )

        return seller_price
