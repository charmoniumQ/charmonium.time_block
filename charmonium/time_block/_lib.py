from typing import Optional


def returns_four(x: Optional[int] = None) -> int:
    """Short description (should be an capitalized and punctuated imperative-verb-phrase or noun-phrase).

    This is the first paragraph in the long description. All sections
    of this doc-string can be styled with `reStructuredText`_.

    .. _`reStructuredText`: https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html

    >>> import charmonium.time_block
    >>> charmonium.time_block.returns_four()
    4
    >>> print("doctest is running")
    doctest is running

    This is the last paragraph of the long description, after which a
    block describes the arguments and returned value in any format accepted by (`napoleon`_).

    .. _`napoleon`: https://www.sphinx-doc.org/en/master/usage/extensions/napoleon.html

    Args:
        x: The value to consume (capitalized and punctuated noun phrase).

    Returns:
        A four (capitalized and punctuated noun phrase).

    """

    return 4
