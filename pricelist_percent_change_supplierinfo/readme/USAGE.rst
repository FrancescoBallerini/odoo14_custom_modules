To use this module, you need to:

Go to Settings > Sales > Pricelist > enable pricelist and select advanced price rules (discounts, formulas).

Create a product, go in 'Purchase tab' and create sellers prices to fill the supplierinfo table.
Alternatively, make purchase orders so the table will fill automatically.

In the product form-view, click the 'Sales tab' in 'Fixed Price' section (which is not fixed price anymore..todo rename it)
and add rule based on other supplierinfo prices.

You can see the selling price recomputing automatically. You will also find a user input and a button "Set Price Discount".

Provide an input and click button to setup the price % discount based on percentage change between computed
selling price (based on supplierinfo price) and your input value.

Attitional notes:
When you add new suppliers, if you don't see price recomputing be sure to save the product form-view
before using this feature (this is not needed when adding pricelist-rules though).
