from ginga import toolkit

if toolkit.family == 'qt':
    from .Widgets import TextSource  # noqa: F401

elif toolkit.family == 'pg':
    from ginga.gw.Widgets import TextSource  # noqa: F401

else:
    raise NotImplementedError("TextSource not implemented for "
                              f"toolkit family '{toolkit.family}'")
