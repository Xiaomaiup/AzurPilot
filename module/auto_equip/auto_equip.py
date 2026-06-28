from module.config.config import TaskEnd
from module.base.button import Button
from module.equipment.equipment import SWIPE_AREA, SWIPE_DISTANCE, SWIPE_RANDOM_RANGE
from module.ui.switch import Switch
from module.exception import ScriptError
from module.logger import logger
from module.retire.assets import SHIP_DETAIL_CHECK
from module.retire.dock import Dock
from module.ui.page import page_dock


AUTO_EQUIP_QUICK_CHANGE = Button(
    area=(1035, 86, 1128, 116),
    color=(90, 125, 185),
    button=(1035, 86, 1128, 116),
    name='AUTO_EQUIP_QUICK_CHANGE',
)

AUTO_EQUIP_QUICK_CHANGE_CHECK = Button(
    area=(1048, 90, 1119, 111),
    color=(239, 174, 117),
    button=(1048, 90, 1119, 111),
    name='AUTO_EQUIP_QUICK_CHANGE_CHECK',
)

AUTO_EQUIP_EQUIPPING_CLICK = Button(
    area=(1035, 245, 1127, 272),
    color=(117, 128, 161),
    button=(1035, 245, 1127, 272),
    name='AUTO_EQUIP_EQUIPPING_CLICK',
)

AUTO_EQUIP_EQUIPPING_ON = Button(
    area=(1035, 248, 1059, 268),
    color=(175, 182, 202),
    button=(1035, 245, 1127, 272),
    name='AUTO_EQUIP_EQUIPPING_ON',
)

AUTO_EQUIP_EQUIPPING_OFF = Button(
    area=(1035, 246, 1066, 270),
    color=(187, 187, 187),
    button=(1035, 245, 1127, 272),
    name='AUTO_EQUIP_EQUIPPING_OFF',
)

auto_equip_equipping_filter = Switch('Auto_equip_equipping_filter')
auto_equip_equipping_filter.add_state(
    'on',
    check_button=AUTO_EQUIP_EQUIPPING_ON,
    click_button=AUTO_EQUIP_EQUIPPING_CLICK,
)
auto_equip_equipping_filter.add_state(
    'off',
    check_button=AUTO_EQUIP_EQUIPPING_OFF,
    click_button=AUTO_EQUIP_EQUIPPING_CLICK,
)


class AutoEquip(Dock):
    def _should_stop(self):
        event = getattr(self.config, 'stop_event', None)
        return event is not None and event.is_set()

    def _quick_change_appear(self):
        return self.appear(AUTO_EQUIP_QUICK_CHANGE_CHECK)

    def _open_quick_change(self):
        logger.info('Open quick equipment change')
        for _ in self.loop(timeout=10):
            if self._quick_change_appear():
                return

            if self.appear(SHIP_DETAIL_CHECK, offset=(30, 30), interval=2):
                self.device.click(AUTO_EQUIP_QUICK_CHANGE)
                continue
            if self.handle_popup_confirm('AUTO_EQUIP_QUICK_CHANGE'):
                continue
            if self.handle_game_tips():
                continue
        else:
            raise ScriptError('Unable to open quick equipment change')

    def _quick_equipping_set(self, enable=True):
        target = 'on' if enable else 'off'
        current = auto_equip_equipping_filter.get(main=self)
        logger.attr('Auto_equip_equipping_filter', current)
        if current == target:
            return
        if current == 'unknown':
            logger.warning('Unable to determine quick equipping filter state')
            return

        self.device.click(AUTO_EQUIP_EQUIPPING_CLICK)
        self.wait_until_stable(AUTO_EQUIP_EQUIPPING_CLICK)

    def _quick_change_next(self):
        logger.info('Swipe to next ship')
        self.device.swipe_vector(
            vector=(-SWIPE_DISTANCE, 0),
            box=SWIPE_AREA.area,
            random_range=SWIPE_RANDOM_RANGE,
            padding=0,
            duration=(0.1, 0.12),
            name='AUTO_EQUIP_SWIPE',
        )
        self.wait_until_stable(SWIPE_AREA)

    def _fill_current_ship_equipment(self):
        logger.hr('Auto equip current ship', level=2)
        self._open_quick_change()
        self._quick_equipping_set(enable=False)
        self.equipment_change_logic()

    def equipment_change_logic(self):
        """
        Placeholder for the actual equipment selection strategy.

        The click framework reaches the quick-change equipment list and turns
        the "equipping" filter off. The ranking/selection logic should
        be implemented here once the coordinate constants and rules are ready.
        """
        logger.info('Equipment change logic placeholder')

    def _ship_limit(self):
        value = getattr(self.config, 'AutoEquip_ShipLimit', 0)
        try:
            value = int(value)
        except (TypeError, ValueError):
            value = 0
        return max(value, 0)

    def run(self):
        logger.hr('Auto Equip', level=1)
        limit = self._ship_limit()
        logger.attr('Ship limit', 'manual stop' if limit == 0 else limit)
        if limit == 0:
            logger.warning('Ship limit is 0, AutoEquip will continue until manually stopped')

        self.ui_ensure(page_dock)
        if not self.dock_enter_first(non_npc=True):
            logger.info('No ship to equip')
            return

        count = 0
        while 1:
            if self._should_stop():
                raise TaskEnd('AutoEquip stopped')

            count += 1
            logger.attr('Ship', count)
            self._fill_current_ship_equipment()

            if limit and count >= limit:
                logger.info('Reached ship limit')
                break

            self._quick_change_next()
