from ginga import toolkit

if toolkit.family == 'qt':
    from .Widgets import TextSource

elif toolkit.family == 'pg':
    from ginga.gw.Widgets import TextSource

else:
    raise NotImplementedError("TextSource not implemented for "
                              f"toolkit family '{toolkit.family}'")
