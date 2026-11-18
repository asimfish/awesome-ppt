# Iris data and method

R. Fisher (1936), *Iris* [dataset]. The UCI Machine Learning Repository publishes the dataset under CC BY 4.0. The file `bezdekIris.data` is an unmodified copy from their archive. [Dataset and citation](https://archive.ics.uci.edu/dataset/53/iris) · [DOI](https://doi.org/10.24432/C56C76) · [Data license](https://creativecommons.org/licenses/by/4.0/) · [Archive](https://archive.ics.uci.edu/static/public/53/iris.zip)

SHA-256 for the unmodified file is `0fed2a99db77ec533a62dc66894d3ec6df3b58b6a8f3cf4a6b47e4086b7f97dc`. Each row supplies one petal-length measurement in centimetres from column three and one species label from column five. The 150 rows form three groups of 50. The derived CSV records each group's count, unweighted mean and observed extrema. The talk rounds chart labels to two decimals. Its row-to-row difference uses the underlying three-decimal means.

From the repository root, `python examples/iris/summarize.py` rebuilds the checked-in summary. Pass an output path to compare the result without modifying the working copy. Numerical derivatives and slide reproductions of these data retain the dataset attribution.
