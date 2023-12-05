
from ginga.gw import Widgets


class ButtonBox(Widgets.HBox):
    def __init__(self):
        super().__init__()

        # TODO: automatically recalculate and resize as needed
        self.btn_width = 30

    def add_widget(self, child):
        wd, ht = child.get_size()
        child.resize(self.btn_width, ht)
        child.cfg_expand(horizontal='minimum')

        super().add_widget(child, stretch=0)
