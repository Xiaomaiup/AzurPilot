import yaml

from module.base.timer import Timer
from module.device.method.utils import HierarchyButton
from module.equipment.assets import *
from module.exception import EmulatorNotRunningError, RequestHumanTakeover
from module.logger import logger
from module.retire.assets import TEMPLATE_BOGUE, TEMPLATE_HERMES, TEMPLATE_RANGER, TEMPLATE_LANGLEY
from module.storage.assets import EQUIPMENT_FULL
from module.storage.storage import StorageHandler

EMPTY_CODE = "MC8wLzAvMC8wXDA="
U2_CONTROL_METHODS = {'uiautomator2', 'minitouch', 'MaaTouch'}
EQUIPMENT_PREVIEW = list([
    EQUIPMENT_CODE_EQUIP_0,
    EQUIPMENT_CODE_EQUIP_1,
    EQUIPMENT_CODE_EQUIP_2,
    EQUIPMENT_CODE_EQUIP_3,
    EQUIPMENT_CODE_EQUIP_4,
    EQUIPMENT_CODE_EQUIP_5,
])


class EquipmentCodeHandler(StorageHandler):
    last_code: str = None

    @property
    def equipment_code_config_key(self):
        return None

    @property
    def equipment_code_export_to_config(self):
        if self.equipment_code_config_key:
            return True
        return self.config.EquipmentCode_ExportToConfig

    def _code_config_load(self):
        key = self.equipment_code_config_key
        if key:
            raw = self.config.cross_get(keys=key)
        else:
            raw = self.config.EquipmentCode_Config

        config = {}
        try:
            for item in yaml.safe_load_all(raw or ''):
                if item:
                    config.update(item)
        except Exception:
            logger.error("Fail to load equipment code config")
        return config

    def _code_config_save(self, config):
        value = yaml.safe_dump(config)
        key = self.equipment_code_config_key
        if key:
            self.config.cross_set(keys=key, value=value)
        else:
            self.config.EquipmentCode_Config = value

    def equipment_code_supported(self):
        method = self.config.Emulator_ControlMethod
        if method in U2_CONTROL_METHODS:
            return True

        logger.warning(
            f"Equipment code requires uiautomator2 based control method, "
            f"current control method is {method}, skip equipment change"
        )
        return False

    def get_code(self, name):
        config = self._code_config_load()
        code = config.get(name)
        if code is None:
            logger.error(f"Config does not contain equipment code for {name}")
        return code

    def set_code(self, name, code):
        config = self._code_config_load()
        try:
            config.update({name: code})
            self._code_config_save(config)
        except Exception:
            logger.error("Fail to set equipment code config")

    def current_ship(self):
        """
        Currently, only supports common CV recognization

        Pages:
            in: equipment_code
        """
        for _ in self.loop():
            if not self.appear(EMPTY_SHIP_R):
                break
        if TEMPLATE_BOGUE.match(self.device.image, scaling=1.46):  # image has rotation
            logger.info("Bogue detected")
            return 'bogue'
        elif TEMPLATE_HERMES.match(self.device.image, scaling=124 / 89):
            logger.info("Hermes detected")
            return 'hermes'
        elif TEMPLATE_RANGER.match(self.device.image, scaling=4 / 3):
            logger.info("Ranger detected")
            return 'ranger'
        elif TEMPLATE_LANGLEY.match(self.device.image, scaling=25 / 21):
            logger.info("Langley detected")
            return 'langley'
        else:
            logger.warning("Unknown ship detected, assuming DD")
            return 'DD'

    def _code_enter(self):
        """
        Pages:
            in: ship_detail
            out: equipment_code
        """
        for _ in self.loop():
            if self.appear(EQUIPMENT_CODE_PAGE_CHECK, offset=(5, 5)):
                break

            if self.appear_then_click(EQUIPMENT_CODE_ENTRANCE, offset=(5, 5), interval=1):
                continue

    def _code_exit(self):
        """
        Pages:
            in: equipment_code
            out: ship_detail
        """
        self.ui_back(check_button=EQUIPMENT_CODE_ENTRANCE)

    def is_code_preview_loaded(self):
        if self.appear(EQUIPMENT_CODE_EQUIP_5_LOCKED, offset=(5, 5)):
            max_index = 5
        else:
            max_index = 6
        for index in range(max_index):
            if not self.appear(EQUIPMENT_PREVIEW[index], offset=(5, 5)):
                return True

        return False

    def _code_preview_clear(self):
        for _ in self.loop(timeout=2):
            if not self.is_code_preview_loaded():
                return True

            if self.appear_then_click(EQUIPMENT_CODE_CLEAR, offset=(5, 5), interval=1):
                continue
        else:
            return False

    def fastinput_ime_enable(self):
        self.device.adb_shell(['am', 'start', '-a', 'android.settings.INPUT_METHOD_SETTINGS'])
        while 1:
            h = self.device.dump_hierarchy_adb()

            def appear(xpath):
                return bool(HierarchyButton(h, xpath))

            def appear_then_click(xpath):
                b = HierarchyButton(h, xpath)
                if b:
                    self.device.click(b)
                    return True
                else:
                    return False

            if appear_then_click('//*[@resource-id="android:id/title" and @text="FastInputIME"]/following-sibling::*[@resource-id="android:id/switch_widget" and @checked="false"]'):
                continue
            if appear_then_click('//*[@resource-id="android:id/button1"]'):
                continue
            # Disable one other enabled IME at a time
            if appear_then_click('(//*[@resource-id="android:id/title" and @text!="FastInputIME"]/following-sibling::*[@resource-id="android:id/switch_widget" and @enabled="true" and @checked="true"])[1]'):
                continue
            if appear('//*[@resource-id="android:id/title" and @text="FastInputIME"]/following-sibling::*[@resource-id="android:id/switch_widget" and @checked="true"]') \
                    and not appear('//*[@resource-id="android:id/title" and @text!="FastInputIME"]/following-sibling::*[@resource-id="android:id/switch_widget" and @enabled="true" and @checked="true"]'):
                break

        self.device.adb_shell(['input', 'keyevent', '4'])

    def set_fastinput_ime(self):
        d = self.device.u2
        try:
            d.set_fastinput_ime(True)
        except Exception:
            logger.warning("FastInputIME not enabled, trying to enable it")
            self.fastinput_ime_enable()

    def _code_input(self, code):
        logger.info(f"Code input: {code}")
        d = self.device.u2
        click_timer = Timer(1, count=3)
        for _ in self.loop():
            name, shown = d.current_ime()
            if shown:
                if name != 'com.github.uiautomator/.FastInputIME':
                    self.set_fastinput_ime()
                    continue
                else:
                    break
            if click_timer.reached_and_reset():
                self.device.click(EQUIPMENT_CODE_TEXTBOX)
        else:
            logger.warning("Equipment code load failed")
            return False
        d.send_keys(text=code, clear=True)
        d.send_action(code="done")
        self.device.sleep((0.3, 0.5))
        for _ in self.loop(timeout=10, skip_first=False):
            _, shown = d.current_ime()
            if shown:
                continue
            if self.is_code_preview_loaded():
                return True
            if self.appear_then_click(EQUIPMENT_CODE_ENTER, offset=(5, 5), interval=3):
                continue
        else:
            logger.warning("Equipment code load failed")
            return False

    def _code_confirm(self):
        logger.info("Code apply")
        for _ in self.loop(timeout=10):
            if self.appear(EQUIPMENT_CODE_ENTRANCE, offset=(5, 5)):
                return True
            if self.appear(EQUIPMENT_FULL, offset=(30, 30)):
                return False
            if self.handle_popup_confirm("EQUIPMENT_CODE"):
                continue
            if self.appear_then_click(EQUIPMENT_CODE_CONFIRM, offset=(5, 5), interval=3):
                continue
        else:
            return False

    def _code_apply(self, code=None):
        for _ in range(5):
            self._code_preview_clear()
            if code is not None and code != EMPTY_CODE:
                success = self._code_input(code)
                if not success:
                    continue
            success = self._code_confirm()
            if success:
                logger.info("Equipment code apply complete.")
                return True
            else:
                self.handle_storage_full()
        else:
            return False

    @staticmethod
    def _code_from_clipboard_output(output):
        if output is None:
            return None
        if isinstance(output, bytes):
            output = output.decode('utf-8', errors='ignore')

        for line in reversed(str(output).splitlines()):
            line = line.strip().strip('\'"')
            if not line:
                continue

            lowered = line.lower()
            if any(text in lowered for text in [
                'not found',
                'unknown command',
                'no primary clip',
                'exception',
                'error:',
                'security exception',
            ]):
                continue

            for prefix in ['text:', 'clipboard text:']:
                if lowered.startswith(prefix):
                    line = line[len(prefix):].strip().strip('\'"')
                    break

            if line.startswith('ClipData') and ':' in line:
                line = line.rsplit(':', 1)[1].strip().strip('\'"')

            # 装备码是无空白的短文本；过滤掉 shell 命令说明等非剪贴板内容。
            if len(line) >= len(EMPTY_CODE) and not any(char.isspace() for char in line):
                return line

        return None

    def _clipboard_adb(self):
        for command in [
            ['cmd', 'clipboard', 'get'],
            ['cmd', 'clipboard', 'get-primary-clip'],
        ]:
            try:
                output = self.device.adb_shell(command, timeout=3)
            except (EmulatorNotRunningError, RequestHumanTakeover):
                raise
            except Exception as e:
                logger.debug(f"通过 ADB 读取剪贴板失败: {e}")
                continue

            code = self._code_from_clipboard_output(output)
            if code is not None:
                logger.info("通过 ADB 读取装备码剪贴板成功")
                return code

        return None

    def _clipboard_uiautomator2(self):
        try:
            output = self.device.clipboard
        except (EmulatorNotRunningError, RequestHumanTakeover):
            raise
        except Exception as e:
            logger.warning(f"通过 uiautomator2 读取剪贴板失败: {e}")
            return None

        code = self._code_from_clipboard_output(output)
        if code is not None:
            logger.info("通过 uiautomator2 读取装备码剪贴板成功")
        return code

    def _clipboard_get(self):
        code = self._clipboard_adb()
        if code is not None:
            return code

        code = self._clipboard_uiautomator2()
        if code is not None:
            return code

        logger.warning("读取装备码剪贴板失败")
        return None

    def _code_export(self):
        self.handle_info_bar()
        for _ in self.loop(timeout=10):
            if self.info_bar_count():
                break
            if self.appear_then_click(EQUIPMENT_CODE_EXPORT, offset=(5, 5), interval=3):
                continue
        return self._clipboard_get()

    def code_clear(self, name=None):
        if not self.equipment_code_supported():
            return False

        self._code_enter()
        if name is None:
            name = self.current_ship()
        if self.equipment_code_export_to_config and self.get_code(name=name) is None:
            self.last_code = self._code_export()
            if self.last_code is None:
                logger.warning("装备码导出失败，跳过清空装备")
                return False
            self.set_code(name=name, code=self.last_code)
        return self._code_apply(code=None)

    def code_apply(self, name=None):
        if not self.equipment_code_supported():
            return False

        self._code_enter()
        if name is None:
            name = self.current_ship()
        code = self.get_code(name=name)
        if code is None:
            code = self.last_code
        if code is None:
            logger.warning("没有可用装备码，跳过装备应用")
            return False
        return self._code_apply(code=code)
