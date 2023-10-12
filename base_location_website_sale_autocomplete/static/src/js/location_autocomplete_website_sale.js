odoo.define("base_location_website_sale_autocomplete.website_sale_extend", function (
    require
) {
    "use strict";

    var core = require("web.core");
    var config = require("web.config");
    var publicWidget = require("web.public.widget");
    require("website_sale.website_sale");

    publicWidget.registry.WebsiteSaleZipcodeAutocomplete = publicWidget.Widget.extend({
        selector: ".website_sale_zipcode_autocomplete",

        events: {
            'change select[name="country_id"]': "_onCountryChange",
            "submit .checkout_address_form_submit": "_onSubmit",
        },

        init: function () {
            this._super.apply(this, arguments);
            this.selected_res_city_zip_id = false;
            // must wait for _changeCountry() debounce, otherwise autocomplete
            // widget will load on "zip" node render position (which will be
            // changed after 500ms) causing overlap on the user input
            this._autocompleteRefresh = _.debounce(
                this._autocompleteRefresh.bind(this),
                500
            );
        },

        /**
         * @Override:
         * Fetch proper source and load autocomplete if source is found
         * for selected country. Sources are 'res.city.zip' records
         * attached to selected country.
         */
        start: function () {
            var def = this._super.apply(this, arguments);
            this._autocompleteRefresh();
            return def;
        },

        //--------------------------------------------------------------------------
        // Handlers
        //--------------------------------------------------------------------------

        /**
         * Country change:
         * Re-fetching the source and rebuild autocomplete or destroy it
         * if there is no source (res.city.zip) for selected country.
         */
        _onCountryChange: function (ev) {
            this._autocompleteRefresh();
        },

        /**
         * Manage UI-autocomplete events after an item has been focused.
         */
        _updateFields: function (event, ui) {
            // ui.item.value/ui.item.label are updated each
            // time user select a "source item".
            // This generally happen with a "click" on an
            // autocomplete item or other events (like arrow down
            // after ui-autocomplete pops-up). We could manage
            // "change" event as well and make some "fallback
            // shenanigans" to retrieve, let's say only state_id
            // instead of cities when user insert a valid zipcode
            // without focusing the widget, but for now we limit
            // to case when ui.item is not null.
            if (ui.hasOwnProperty("item") && ui.item != null) {
                // Make an rpc by matching selected "label" with
                // "display_name" to retrieve other fields from city
                var self = this;
                var prom = this._rpc({
                    model: "res.city.zip",
                    method: "search_read",
                    kwargs: {
                        domain: [["display_name", "=", ui.item.label]],
                        limit: 1,
                        fields: ["display_name", "city_id", "state_id"],
                    },
                }).then(function (result) {
                    var self2 = self;
                    if (Object.keys(result).length > 0) {
                        // fill "state_id" and "city_id" on form-view
                        $("select[name='state_id']").val(result[0].state_id[0]);
                        $("input[name='city']").val(result[0].city_id[1]);
                        if (result[0].hasOwnProperty("id")) {
                            // store the 'res.city.zip' record, we need it on submit
                            // to set zip_id rec on 'res.partner' backend.
                            self2.selected_res_city_zip_id = result[0].id;
                        }
                    }
                });
                return prom;
            }
        },

        /**
         *  Set "zip_id" field on backend with a different controller
         *  to bypass "details_form_validate()": there is no need to
         *  validate this field since it's value is a consequence of
         *  user choice on "zipcode" input, so we call write() to avoid
         *  loading huge number of zip records on html.
         *  Despite skipping controller validation this query has to be
         *  done on Submit (when all form fields passed validation) in
         *  order to ensure data consistency in case of transaction rollback.
         */
        _onSubmit: function (ev) {
            var self = this;
            var def = this._super.apply(this, arguments).then(function (r) {
                self._rpc({
                    route: "/shop/address/on_submit_zipcode_autocomplete",
                    params: {
                        selected_res_city_zip_id: self.selected_res_city_zip_id,
                    },
                });
            });
            return def;
        },

        //--------------------------------------------------------------------------
        // Private
        //--------------------------------------------------------------------------

        /**
         * Call method to update source, then manage ui-autocomplete:
         * if a source length is returned, load the widget and attach
         * it to zip input. If no source is returned for selected
         * country destroy widget, in case it was active before.
         */
        _autocompleteRefresh: function () {
            var country_id = parseInt($("select[name='country_id']").val());
            var self = this;
            // update source
            this._fetchAutocompleteSource(country_id).then(function (acList) {
                if (Object.keys(acList).length > 0) {
                    var position = {collision: "flip"};
                    var minLength = 3;
                    if (config.device.isMobile || config.device.isMobileDevice) {
                        // on small screen avoid covering input while user still typing
                        // isMobile true when screen-size: XS/VSM/SM
                        minLength = 5;
                    }
                    // append autocomplete to zipcode input
                    $("input[name='zip']").autocomplete({
                        source: function (request, response) {
                            var matches = $.map(acList, function (acItem) {
                                if (acItem.value.indexOf(request.term) === 0) {
                                    return acItem;
                                }
                            });
                            response(matches);
                        },
                        minLength: minLength,
                        position: position,
                        select: function (event, ui) {
                            // set vals in form-view on item select
                            self._updateFields(event, ui);
                        },
                    });
                } else if ($("input[name='zip']").autocomplete("instance")) {
                    $("input[name='zip']").autocomplete("destroy");
                }
            });
        },

        /**
         * Get autocomplete source by calling python controller
         */
        _fetchAutocompleteSource: function (countryID) {
            var def = this._rpc({
                route: "/shop/address/get_zipcode_autocomplete_source",
                params: {
                    country_id: countryID,
                },
            }).then(function (result) {
                return result.autocomplete_source;
            });
            return def;
        },
    });
});
