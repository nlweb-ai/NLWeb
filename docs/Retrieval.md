# Retrieval

At this point, only one of the stores is queried. In future, we will query all the available stores. We do not assume that the backend is a vector store.

We do assume that the vector store will return a list of the database items encoded as json objects, preferably in a schema.org schema.

We are in the process of adding Restful vector stores, which will enable one NLWeb instance to treat another as its backend.

A significant improvement to retrieval would be the following. Consider a query like "homes costing less than 500k which would be suitable `for a family with 2 small children and a large dog". The database of items (real estate listings) will have structured fields like the price. It would be good to translate this into a combination of
