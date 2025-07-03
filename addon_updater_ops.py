# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

import os
import sys
from subprocess import call

import bpy #type: ignore
from bpy.app.handlers import persistent #type: ignore


try:
    from .addon_updater import Updater
except Exception as e:
    print("初始化更新程序时出错")
    print(str(e))


    class SingletonUpdaterNone(object):
        def __init__(self):
            self.addon = None
            self.verbose = False
            self.invalid_updater = True
            self.error = None
            self.error_msg = None
            self.async_checking = None

        def clear_state(self):
            self.addon = None
            self.verbose = False
            self.invalid_updater = True
            self.error = None
            self.error_msg = None
            self.async_checking = None

        def run_update(self): pass

        def check_for_update(self): pass


    Updater = SingletonUpdaterNone()
    Updater.error = "Error initializing updater module"
    Updater.error_msg = str(e)

Updater.addon = "quickimportxxmi"


def layout_split(layout, factor=0.0, align=False):
    if not hasattr(bpy.app, "version") or bpy.app.version < (2, 80):
        return layout.split(percentage=factor, align=align)
    return layout.split(factor=factor, align=align)


def get_user_preferences(context=None):
    if not context:
        context = bpy.context
    prefs = None
    if hasattr(context, "user_preferences"):
        prefs = context.user_preferences.addons.get(__package__, None)
    elif hasattr(context, "preferences"):
        prefs = context.preferences.addons.get(__package__, None)
    if prefs:
        return prefs.preferences
    return None

def make_annotations(cls):
    """Add annotation attribute to fields to avoid Blender 2.8+ warnings"""
    if not hasattr(bpy.app, "version") or bpy.app.version < (2, 80):
        return cls
    if bpy.app.version < (2, 93, 0):
        bl_props = {k: v for k, v in cls.__dict__.items()
                    if isinstance(v, tuple)}
    else:
        bl_props = {k: v for k, v in cls.__dict__.items()
                    if isinstance(v, bpy.props._PropertyDeferred)}
    if bl_props:
        if '__annotations__' not in cls.__dict__:
            setattr(cls, '__annotations__', {})
        annotations = cls.__dict__['__annotations__']
        for k, v in bl_props.items():
            annotations[k] = v
            delattr(cls, k)
    return cls

def get_update_post():
    if hasattr(bpy.app.handlers, 'scene_update_post'):
        return bpy.app.handlers.scene_update_post
    else:
        return bpy.app.handlers.depsgraph_update_post


class AddonUpdaterInstallPopup(bpy.types.Operator):
    bl_label = "更新快速导入"
    bl_idname = Updater.addon + ".updater_install_popup"
    bl_description = "显示当前可用更新的弹窗菜单"
    bl_options = {'REGISTER', 'INTERNAL'}

    clean_install = bpy.props.BoolProperty(
        name="纯净安装",
        description="若启用，将在安装新版本前完全清除插件目录，执行全新安装",
        default=False,
        options={'HIDDEN'}
    )
    ignore_enum = bpy.props.EnumProperty(
        name="更新处理",
        description="选择如何处理当前更新",
        items=[
            ("install", "立即更新", "立即安装新版本"),
            ("ignore", "忽略", "忽略此版本更新并不再提醒"),
            ("defer", "稍后", "下次启动时再决定")
        ],
        options={'HIDDEN'}
    )

    def check(self, context):
        return True

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        if Updater.invalid_updater is True:
            layout.label(text="更新器模块错误")
            return
        elif Updater.update_ready is True:
            col = layout.column()
            col.scale_y = 0.7
            col.label(text="{} 更新可用！".format(str(Updater.update_version)),
                     icon="LOOP_FORWARDS")
            col.label(text="选择'立即更新'并按确定进行安装", icon="BLANK1")
            col.label(text="或点击窗口外区域延迟更新", icon="BLANK1")
            row = col.row()
            row.prop(self, "ignore_enum", expand=True)
            col.split()
        elif Updater.update_ready is False:
            col = layout.column()
            col.scale_y = 0.7
            col.label(text="暂无可用更新")
            col.label(text="按确定关闭对话框")
        else:
            layout.label(text="立即检查更新？")

    def execute(self, context):

        if Updater.invalid_updater is True:
            return {'CANCELLED'}

        if Updater.manual_only is True:
            bpy.ops.wm.url_open(url=Updater.website)
        elif Updater.update_ready is True:

            if self.ignore_enum == 'defer':
                return {'FINISHED'}
            elif self.ignore_enum == 'ignore':
                Updater.ignore_update()
                return {'FINISHED'}

            res = Updater.run_update(force=False,
                                   callback=post_update_callback,
                                   clean=self.clean_install)
            if Updater.verbose:
                if res == 0:
                    print("更新器返回成功")
                else:
                    print("更新器返回错误代码: {}".format(res))
        elif Updater.update_ready is None:
            _ = Updater.check_for_update(now=True)

            atr = AddonUpdaterInstallPopup.bl_idname.split(".")
            getattr(getattr(bpy.ops, atr[0]), atr[1])('INVOKE_DEFAULT')
        else:
            if Updater.verbose:
                print("无需操作，更新未就绪")
        return {'FINISHED'}


class AddonUpdaterCheckNow(bpy.types.Operator):
    bl_label = "立即检查更新"
    bl_idname = Updater.addon + ".updater_check_now"
    bl_description = "立即检查快速导入的更新" 
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        if Updater.invalid_updater is True:
            return {'CANCELLED'}

        if Updater.async_checking is True and Updater.error is None:
            return {'CANCELLED'}

        settings = get_user_preferences(context)
        if not settings:
            if Updater.verbose:
                print("无法获取{}首选项，跳过更新检查".format(__package__))
            return {'CANCELLED'}
        
        # 删除启用关键字参数，因为它不是预期的
        Updater.set_check_interval(months=settings.updater_interval_months,
                                   days=settings.updater_interval_days,
                                   hours=settings.updater_interval_hours,
                                   minutes=settings.updater_interval_minutes)
        Updater.check_for_update_now(ui_refresh)
        return {'FINISHED'}


class AddonUpdaterUpdateNow(bpy.types.Operator):
    bl_label = "立即更新插件"
    bl_idname = Updater.addon + ".updater_update_now"
    bl_description = "更新至快速导入的最新版本"
    bl_options = {'REGISTER', 'INTERNAL'}

    clean_install = bpy.props.BoolProperty(
        name="纯净安装",
        description="若启用，将在安装新版本前完全清除插件目录，执行全新安装",
        default=False,
        options={'HIDDEN'}
    )

    def execute(self, context):

        if Updater.invalid_updater is True:
            return {'CANCELLED'}

        if Updater.manual_only is True:
            bpy.ops.wm.url_open(url=Updater.website)
        if Updater.update_ready is True:
            # 如果失败，则建议打开网站
            try:
                res = Updater.run_update(force=False,
                                         callback=post_update_callback,
                                         clean=self.clean_install)

                if Updater.verbose:
                    if res == 0:
                        print("更新器返回成功")
                    else:
                        print("更新器返回代码：" + str(res))
            except Exception as ex:
                Updater._error = "尝试更新时发生错误"
                Updater._error_msg = str(ex)
                atr = AddonUpdaterInstallManually.bl_idname.split(".")
                getattr(getattr(bpy.ops, atr[0]), atr[1])('INVOKE_DEFAULT')
        elif Updater.update_ready is None:
            update_ready, version, link = Updater.check_for_update(now=True)
            atr = AddonUpdaterInstallPopup.bl_idname.split(".")
            getattr(getattr(bpy.ops, atr[0]), atr[1])('INVOKE_DEFAULT')

        elif Updater.update_ready is False:
            self.report({'INFO'}, "无需更新")
        else:
            self.report({'ERROR'}, "更新过程中发生错误")

        return {'FINISHED'}


class AddonUpdaterUpdateTarget(bpy.types.Operator):
    bl_label = "插件版本目标"
    bl_idname = Updater.addon + ".updater_update_target"
    bl_description = "安装指定版本的快速导入"
    bl_options = {'REGISTER', 'INTERNAL'}

    def target_version(self, _):
        ret = []
        i = 0
        for tag in Updater.tags:
            ret.append((tag, tag, "安装此版本：" + tag))
            i += 1
        return ret

    target = bpy.props.EnumProperty(
        name="目标安装版本",
        description="选择要安装的版本",
        items=target_version
    )

    clean_install = bpy.props.BoolProperty(
        name="纯净安装",
        description="若启用，将在安装新版本前完全清除插件目录，执行全新安装",
        default=False,
        options={'HIDDEN'}
    )

    @classmethod
    def poll(cls, _):
        if Updater.invalid_updater is True:
            return False
        return Updater.update_ready is not None and len(Updater.tags) > 0

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        if Updater.invalid_updater is True:
            layout.label(text="更新模块初始化失败")
            return
        split = layout_split(layout, factor=0.66)
        subcol = split.column()
        subcol.label(text="选择回滚版本")
        subcol = split.column()
        subcol.prop(self, "target", text="")

    def execute(self, context):

        if Updater.invalid_updater is True:
            return {'CANCELLED'}

        res = Updater.run_update(force=False,
                               revert_tag=self.target,
                               callback=post_update_callback,
                               clean=self.clean_install)

        if res == 0:
            if Updater.verbose:
                print("更新成功完成")
        else:
            if Updater.verbose:
                print(f"更新失败，错误代码: {res}")
            return {'CANCELLED'}

        return {'FINISHED'}


class AddonUpdaterInstallManually(bpy.types.Operator):
    bl_label = "手动安装更新"
    bl_idname = Updater.addon + ".updater_install_manually"
    bl_description = "手动安装插件更新版本"
    bl_options = {'REGISTER', 'INTERNAL'}

    error = bpy.props.StringProperty(
        name="错误信息",
        default="",
        options={'HIDDEN'}
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self)

    def draw(self, context):
        layout = self.layout

        if Updater.invalid_updater is True:
            layout.label(text="更新器错误")
            return

        if self.error != "":
            col = layout.column()
            col.scale_y = 0.7
            col.label(text="自动安装时发生问题", icon="ERROR")
            col.label(text="点击下方下载按钮并安装", icon="BLANK1")
            col.label(text="像普通插件一样安装zip文件", icon="BLANK1")
        else:
            col = layout.column()
            col.scale_y = 0.7
            col.label(text="请手动安装插件")
            col.label(text="点击下方下载按钮并安装")
            col.label(text="像普通插件一样安装zip文件")

        row = layout.row()

        if Updater.update_link is not None:
            row.operator("wm.url_open",
                         text="直接下载").url = Updater.update_link
        else:
            row.operator("wm.url_open",
                         text="(无法获取直接下载链接)")
            row.enabled = False

            if Updater.website is not None:
                row = layout.row()
                row.operator("wm.url_open", text="打开官网").url = Updater.website
            else:
                row = layout.row()
                row.label(text="请访问来源网站下载更新")

    def execute(self, context):
        return {'FINISHED'}


class AddonUpdaterUpdatedSuccessful(bpy.types.Operator):
    bl_label = "安装报告"
    bl_idname = Updater.addon + ".updater_update_successful"
    bl_description = "更新安装结果反馈"
    bl_options = {'REGISTER', 'INTERNAL', 'UNDO'}

    error = bpy.props.StringProperty(
        name="错误信息",
        default="",
        options={'HIDDEN'}
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_popup(self, event)

    def draw(self, context):
        layout = self.layout

        if Updater.invalid_updater is True:
            layout.label(text="更新器错误")
            return

        saved = Updater.json
        if self.error != "":
            col = layout.column()
            col.scale_y = 0.7
            col.label(text="发生错误，未能安装", icon="ERROR")
            if Updater.error_msg:
                msg = Updater.error_msg
            else:
                msg = self.error
            col.label(text=str(msg), icon="BLANK1")
            rw = col.row()
            rw.scale_y = 2
            rw.operator("wm.url_open",
                        text="点击手动下载",
                        icon="BLANK1").url = Updater.website

        elif Updater.auto_reload_post_update is False:
            if "just_restored" in saved and saved["just_restored"] is True:
                col = layout.column()
                col.scale_y = 0.7
                col.label(text="插件已恢复", icon="RECOVER_LAST")
                col.label(text="请重启Blender以重新加载", icon="BLANK1")
                Updater.json_reset_restore()
            else:
                col = layout.column()
                col.scale_y = 0.7
                col.label(text="插件安装成功", icon="FILE_TICK")
                col.label(text="请重启Blender以重新加载", icon="BLANK1")

        else:
            if "just_restored" in saved and saved["just_restored"] is True:
                col = layout.column()
                col.scale_y = 0.7
                col.label(text="插件已恢复", icon="RECOVER_LAST")
                col.label(text="建议重启Blender以完全重新加载", icon="BLANK1")
                Updater.json_reset_restore()
            else:
                col = layout.column()
                col.scale_y = 0.7
                col.label(text="插件安装成功", icon="FILE_TICK")
                col.label(text="建议重启Blender以完全重新加载", icon="BLANK1")

    def execute(self, context):
        return {'FINISHED'}


class AddonUpdaterRestoreBackup(bpy.types.Operator):
    bl_label = "恢复备份"
    bl_idname = Updater.addon + ".updater_restore_backup"
    bl_description = "从备份恢复插件"
    bl_options = {'REGISTER', 'INTERNAL'}

    @classmethod
    def poll(cls, _):
        try:
            return os.path.isdir(os.path.join(Updater.stage_path, "backup"))
        except OSError:
            return False

    def execute(self, context):
        if Updater.invalid_updater is True:
            return {'CANCELLED'}
        Updater.restore_backup()
        return {'FINISHED'}


class AddonUpdaterIgnore(bpy.types.Operator):
    bl_label = "忽略更新"
    bl_idname = Updater.addon + ".updater_ignore"
    bl_description = "忽略此版本更新并不再提醒"
    bl_options = {'REGISTER', 'INTERNAL'}

    @classmethod
    def poll(cls, _):
        if Updater.invalid_updater is True:
            return False
        elif Updater.update_ready is True:
            return True
        else:
            return False

    def execute(self, context):
        if Updater.invalid_updater is True:
            return {'CANCELLED'}
        Updater.ignore_update()
        self.report({"INFO"}, "Open addon preferences for updater options")
        return {'FINISHED'}


class AddonUpdaterEndBackground(bpy.types.Operator):
    bl_label = "停止后台检查"
    bl_idname = Updater.addon + ".end_background_check"
    bl_description = "停止后台更新检查流程"
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        # 当更新模块导入出错时
        if Updater.invalid_updater is True:
            return {'CANCELLED'}
        Updater.stop_async_check_update()
        return {'FINISHED'}


ran_autocheck_install_popup = False
ran_update_sucess_popup = False

ran_background_check = False


@persistent
def updater_run_success_popup_handler(_):
    global ran_update_sucess_popup
    ran_update_sucess_popup = True

    if Updater.invalid_updater is True:
        return

    try:
        get_update_post().remove(updater_run_success_popup_handler)
    except ValueError:
        pass

    atr = AddonUpdaterUpdatedSuccessful.bl_idname.split(".")
    getattr(getattr(bpy.ops, atr[0]), atr[1])('INVOKE_DEFAULT')


@persistent
def updater_run_install_popup_handler(_):
    global ran_autocheck_install_popup
    ran_autocheck_install_popup = True

    if Updater.invalid_updater is True:
        return

    try:
        get_update_post().remove(updater_run_install_popup_handler)
    except ValueError:
        pass

    if "ignore" in Updater.json and Updater.json["ignore"] is True:
        return
    elif "version_text" in Updater.json and "version" in Updater.json["version_text"]:
        version = Updater.json["version_text"]["version"]
        ver_tuple = Updater.version_tuple_from_text(version)

        if ver_tuple < Updater.current_version:
            if Updater.verbose:
                print("{} 更新器：检测到用户已完成更新，正在清除标志".format(Updater.addon))
            Updater.json_reset_restore()
            return
    atr = AddonUpdaterInstallPopup.bl_idname.split(".")
    getattr(getattr(bpy.ops, atr[0]), atr[1])('INVOKE_DEFAULT')


def background_update_callback(update_ready):
    global ran_autocheck_install_popup

    if Updater.invalid_updater is True:
        return
    if Updater.showpopups is False:
        return
    if update_ready is not True:
        return
    if updater_run_install_popup_handler not in get_update_post() and ran_autocheck_install_popup is False:
        get_update_post().append(updater_run_install_popup_handler)
        ran_autocheck_install_popup = True


def post_update_callback(_, res=None):
    if Updater.invalid_updater is True:
        return

    if res is None:
        if Updater.verbose:
            print("{} 更新器：正在执行更新后回调".format(Updater.addon))

        atr = AddonUpdaterUpdatedSuccessful.bl_idname.split(".")
        getattr(getattr(bpy.ops, atr[0]), atr[1])('INVOKE_DEFAULT')
        global ran_update_sucess_popup
        ran_update_sucess_popup = True
    else:
        atr = AddonUpdaterUpdatedSuccessful.bl_idname.split(".")
        getattr(getattr(bpy.ops, atr[0]), atr[1])('INVOKE_DEFAULT', error=res)
    return


def ui_refresh(_):
    for windowManager in bpy.data.window_managers:
        for window in windowManager.windows:
            for area in window.screen.areas:
                area.tag_redraw()


def check_for_update_background():
    if Updater.invalid_updater is True:
        return
    global ran_background_check
    if ran_background_check is True:
        return
    elif Updater.update_ready is not None or Updater.async_checking is True:
        return

    settings = get_user_preferences(bpy.context)
    if not settings:
        return
    Updater.set_check_interval(enable=settings.auto_check_update,
                               months=settings.updater_interval_months,
                               days=settings.updater_intrval_days,
                               hours=settings.updater_intrval_hours,
                               minutes=settings.updater_intrval_minutes)

    if Updater.verbose:
        print("{} 更新器：正在后台检查更新".format(Updater.addon))
    Updater.check_for_update_async(background_update_callback)
    ran_background_check = True


def check_for_update_nonthreaded(self, _):
    if Updater.invalid_updater is True:
        return

    settings = get_user_preferences(bpy.context)
    if not settings:
        if Updater.verbose:
            print("无法获取 {} 首选项，已跳过更新检查".format(
                __package__))
        return
    Updater.set_check_interval(enable=settings.auto_check_update,
                               months=settings.updater_interval_months,
                               days=settings.updater_intrval_days,
                               hours=settings.updater_intrval_hours,
                               minutes=settings.updater_intrval_minutes)

    update_ready, version, link = Updater.check_for_update(now=False)
    if update_ready is True:
        atr = AddonUpdaterInstallPopup.bl_idname.split(".")
        getattr(getattr(bpy.ops, atr[0]), atr[1])('INVOKE_DEFAULT')
    else:
        if Updater.verbose:
            print("暂无可用更新")
        self.report({'INFO'}, "No update ready")


def show_reload_popup():
    if not hasattr(Updater, 'invalid_updater') or Updater.invalid_updater is True:
        return
    saved_state = Updater.json
    global ran_update_sucess_popup

    a = saved_state is not None
    b = "just_updated" in saved_state
    c = saved_state["just_updated"]

    if a and b and c:
        Updater.json_reset_postupdate()

        if Updater.auto_reload_post_update is False:
            return

        if updater_run_success_popup_handler not in get_update_post() and ran_update_sucess_popup is False:
            get_update_post().append(updater_run_success_popup_handler)
            ran_update_sucess_popup = True


def update_notice_box_ui(self, _):
    if Updater.invalid_updater is True:
        return

    saved_state = Updater.json
    if Updater.auto_reload_post_update is False:
        if "just_updated" in saved_state and saved_state["just_updated"] is True:
            layout = self.layout
            box = layout.box()
            col = box.column()
            col.scale_y = 0.7
            col.label(text="重启Blender", icon="ERROR")
            col.label(text="以完成更新")
            return

    if "ignore" in Updater.json and Updater.json["ignore"] is True:
        return
    if Updater.update_ready is not True:
        return

    layout = self.layout
    box = layout.box()
    col = box.column(align=True)
    col.label(text="更新已就绪！", icon="ERROR")
    col.separator()
    row = col.row(align=True)
    split = row.split(align=True)
    col_l = split.column(align=True)
    col_l.scale_y = 1.5
    col_l.operator(AddonUpdaterIgnore.bl_idname, icon="X", text="忽略")
    col_r = split.column(align=True)
    col_r.scale_y = 1.5
    if Updater.manual_only is False:
        col_r.operator(AddonUpdaterUpdateNow.bl_idname, text="更新", icon="LOOP_FORWARDS")
        col.operator("wm.url_open", text="打开官网").url = Updater.website
        col.operator(AddonUpdaterInstallManually.bl_idname, text="手动安装")
    else:
        col.operator("wm.url_open", text="立即获取").url = Updater.website


def update_settings_ui(self, context, element=None):
    """首选项 - 用于在用户首选项面板内以全宽绘制

    该函数可在用户首选项面板内运行，用于首选项 UI。
    放置在 UI 绘制中，使用：
    addon_Updater_ops.update_settings_ui(self, context)
    或：
    addon_Updater_ops.update_settings_ui(context)
    """

    # Element 是一个 UI 元素，例如布局、行、列或框。
    if element is None:
        element = self.layout
    box = element.box()

    # 以防导入更新程序时出现错误。
    if Updater.invalid_updater:
        box.label(text="初始化更新器错误：")
        box.label(text=Updater.error_msg)
        return
    settings = get_user_preferences(context)
    if not settings:
        box.label(text="获取更新器首选项错误", icon='ERROR')
        return

    # 自动更新设置
    box.label(text="更新器设置")
    row = box.row()

    # 特殊情况，告诉用户重新启动Blender，如果这样设置
    if not Updater.auto_reload_post_update:
        saved_state = Updater.json
        if "just_updated" in saved_state and saved_state["just_updated"]:
            row.alert = True
            row.operator("wm.quit_blender",
                         text="重启Blender以完成更新",
                         icon="ERROR")
            return

    split = layout_split(row, factor=0.4)
    sub_col = split.column()
    sub_col.prop(settings, "auto_check_update")
    sub_col = split.column()

    if not settings.auto_check_update:
        sub_col.enabled = False
    sub_row = sub_col.row()
    sub_row.label(text="检查间隔时间")
    sub_row = sub_col.row(align=True)
    check_col = sub_row.column(align=True)
    check_col.prop(settings, "updater_interval_months")
    check_col = sub_row.column(align=True)
    check_col.prop(settings, "updater_interval_days")
    check_col = sub_row.column(align=True)

    # 考虑取消注释以用于本地开发（例如，设置更短的间隔）
    # check_col.prop(settings,"Updater_interval_hours")
    # check_col = sub_row.column(align=True)
    # check_col.prop(settings,"Updater_interval_minutes")

    # 检查/管理更新。
    row = box.row()
    col = row.column()
    if Updater.error is not None:
        sub_col = col.row(align=True)
        sub_col.scale_y = 1
        split = sub_col.split(align=True)
        split.scale_y = 2
        if "ssl" in Updater.error_msg.lower():
            split.enabled = True
            split.operator(AddonUpdaterInstallManually.bl_idname,
                           text=Updater.error)
        else:
            split.enabled = False
            split.operator(AddonUpdaterCheckNow.bl_idname,
                           text=Updater.error)
        split = sub_col.split(align=True)
        split.scale_y = 2
        split.operator(AddonUpdaterCheckNow.bl_idname,
                       text="", icon="FILE_REFRESH")

    elif Updater.update_ready is None and not Updater.async_checking:
        col.scale_y = 2
        col.operator(AddonUpdaterCheckNow.bl_idname)
    elif Updater.update_ready is None: # 异步正在运行
        sub_col = col.row(align=True)
        sub_col.scale_y = 1
        split = sub_col.split(align=True)
        split.enabled = False
        split.scale_y = 2
        split.operator(AddonUpdaterCheckNow.bl_idname, text="检查中...")
        split = sub_col.split(align=True)
        split.scale_y = 2
        split.operator(AddonUpdaterEndBackground.bl_idname, text="", icon="X")

    elif Updater.include_branches and \
            len(Updater.tags) == len(Updater.include_branch_list) and not \
            Updater.manual_only:
        # 未找到版本，但仍显示适当的分支。
        sub_col = col.row(align=True)
        sub_col.scale_y = 1
        split = sub_col.split(align=True)
        split.scale_y = 2
        update_now_txt = "直接更新至{}".format(
            Updater.include_branch_list[0])
        split.operator(AddonUpdaterUpdateNow.bl_idname, text=update_now_txt)
        split = sub_col.split(align=True)
        split.scale_y = 2
        split.operator(AddonUpdaterCheckNow.bl_idname,
                       text="", icon="FILE_REFRESH")

    elif Updater.update_ready and not Updater.manual_only:
        sub_col = col.row(align=True)
        sub_col.scale_y = 1
        split = sub_col.split(align=True)
        split.scale_y = 2
        split.operator(AddonUpdaterUpdateNow.bl_idname,
                       text="立即更新至" + str(Updater.update_version))
        split = sub_col.split(align=True)
        split.scale_y = 2
        split.operator(AddonUpdaterCheckNow.bl_idname,
                       text="", icon="FILE_REFRESH")

    elif Updater.update_ready and Updater.manual_only:
        col.scale_y = 2
        dl_now_txt = "下载" + str(Updater.update_version)
        col.operator("wm.url_open",
                     text=dl_now_txt).url = Updater.website
    else: # 即 Updater.update_ready == False。
        sub_col = col.row(align=True)
        sub_col.scale_y = 1
        split = sub_col.split(align=True)
        split.enabled = False
        split.scale_y = 2
        split.operator(AddonUpdaterCheckNow.bl_idname,
                       text="插件已是最新版本")
        split = sub_col.split(align=True)
        split.scale_y = 2
        split.operator(AddonUpdaterCheckNow.bl_idname,
                       text="", icon="FILE_REFRESH")

    if not Updater.manual_only:
        col = row.column(align=True)
        if Updater.include_branches and len(Updater.include_branch_list) > 0:
            branch = Updater.include_branch_list[0]
            col.operator(AddonUpdaterUpdateTarget.bl_idname,
                         text="安装{}或旧版本".format(branch))
        else:
            col.operator(AddonUpdaterUpdateTarget.bl_idname,
                         text="重新安装插件版本")
        last_date = "无可用备份"
        backup_path = os.path.join(Updater.stage_path, "backup")
        if "backup_date" in Updater.json and os.path.isdir(backup_path):
            if Updater.json["backup_date"] == "":
                last_date = "日期未知"
            else:
                last_date = Updater.json["backup_date"]
        backup_text = "恢复插件备份（{}）".format(last_date)
        col.operator(AddonUpdaterRestoreBackup.bl_idname, text=backup_text)

    row = box.row()
    row.scale_y = 0.7
    last_check = Updater.json["last_check"]
    if Updater.error is not None and Updater.error_msg is not None:
        row.label(text=Updater.error_msg)
    elif last_check:
        last_check = last_check[0: last_check.index(".")]
        row.label(text="上次更新检查：" + last_check)
    else:
        row.label(text="上次更新检查：从未检查")


def update_settings_ui_condensed(self, context, element=None):
    if element is None:
        element = self.layout
    row = element.row()

    if Updater.invalid_updater is True:
        row.label(text="初始化更新器错误：")
        row.label(text=Updater.error_msg)
        return

    settings = get_user_preferences(context)

    if not settings:
        row.label(text="获取更新器首选项错误", icon='ERROR')
        return

    if Updater.auto_reload_post_update is False:
        saved_state = Updater.json
        if "just_updated" in saved_state and saved_state["just_updated"] is True:
            row.label(text="重启Blender以完成更新", icon="ERROR")
            return

    col = row.column()
    if Updater.error is not None:
        subcol = col.row(align=True)
        subcol.scale_y = 1
        split = subcol.split(align=True)
        split.scale_y = 2
        if "ssl" in Updater.error_msg.lower():
            split.enabled = True
            split.operator(AddonUpdaterInstallManually.bl_idname, text=Updater.error)
        else:
            split.enabled = False
            split.operator(AddonUpdaterCheckNow.bl_idname, text=Updater.error)
        split = subcol.split(align=True)
        split.scale_y = 2
        split.operator(AddonUpdaterCheckNow.bl_idname, text="", icon="FILE_REFRESH")

    elif Updater.update_ready is None and Updater.async_checking is False:
        col.scale_y = 2
        col.operator(AddonUpdaterCheckNow.bl_idname)
    elif Updater.update_ready is None:
        subcol = col.row(align=True)
        subcol.scale_y = 1
        split = subcol.split(align=True)
        split.enabled = False
        split.scale_y = 2
        split.operator(AddonUpdaterCheckNow.bl_idname, text="检查中...")
        split = subcol.split(align=True)
        split.scale_y = 2
        split.operator(AddonUpdaterEndBackground.bl_idname, text="", icon="X")

    elif Updater.include_branches is True and len(
            Updater.tags) == len(Updater.include_branch_list) and Updater.manual_only is False:
        subcol = col.row(align=True)
        subcol.scale_y = 1
        split = subcol.split(align=True)
        split.scale_y = 2
        split.operator(AddonUpdaterUpdateNow.bl_idname,
                       text="直接更新至" + str(Updater.include_branch_list[0]))
        split = subcol.split(align=True)
        split.scale_y = 2
        split.operator(AddonUpdaterCheckNow.bl_idname, text="", icon="FILE_REFRESH")

    elif Updater.update_ready is True and Updater.manual_only is False:
        subcol = col.row(align=True)
        subcol.scale_y = 1
        split = subcol.split(align=True)
        split.scale_y = 2
        split.operator(AddonUpdaterUpdateNow.bl_idname,
                       text="立即更新至" + str(Updater.update_version))
        split = subcol.split(align=True)
        split.scale_y = 2
        split.operator(AddonUpdaterCheckNow.bl_idname, text="", icon="FILE_REFRESH")

    elif Updater.update_ready is True and Updater.manual_only is True:
        col.scale_y = 2
        col.operator("wm.url_open", text="下载" + str(Updater.update_version)).url = Updater.website
    else:
        subcol = col.row(align=True)
        subcol.scale_y = 1
        split = subcol.split(align=True)
        split.enabled = False
        split.scale_y = 2
        split.operator(AddonUpdaterCheckNow.bl_idname, text="插件已是最新版本")
        split = subcol.split(align=True)
        split.scale_y = 2
        split.operator(AddonUpdaterCheckNow.bl_idname, text="", icon="FILE_REFRESH")

    row = element.row()
    row.prop(settings, "auto_check_update")

    row = element.row()
    row.scale_y = 0.7
    lastcheck = Updater.json["last_check"]
    if Updater.error is not None and Updater.error_msg is not None:
        row.label(text=Updater.error_msg)
    elif lastcheck != "" and lastcheck is not None:
        lastcheck = lastcheck[0: lastcheck.index(".")]
        row.label(text="上次检查：" + lastcheck)
    else:
        row.label(text="上次检查：从未检查")


def skip_tag_function(self, tag):
    if self.invalid_updater is True:
        return False

    if self.include_branches is True:
        for branch in self.include_branch_list:
            if tag["name"].lower() == branch:
                return False

    tupled = self.version_tuple_from_text(tag["name"])
    if not isinstance(tupled, tuple):
        return True

    if self.version_min_update is not None:
        if tupled < self.version_min_update:
            return True

    if self.version_max_update is not None:
        if tupled >= self.version_max_update:
            return True

    return False


def select_link_function(tag):
    link = tag["zipball_url"]
    return link


classes = (
    AddonUpdaterInstallPopup,
    AddonUpdaterCheckNow,
    AddonUpdaterUpdateNow,
    AddonUpdaterUpdateTarget,
    AddonUpdaterInstallManually,
    AddonUpdaterUpdatedSuccessful,
    AddonUpdaterRestoreBackup,
    AddonUpdaterIgnore,
    AddonUpdaterEndBackground
)


def register(bl_info):
    if Updater.error:
        print("正在退出更新器注册，" + Updater.error)
        return

    Updater.clear_state()
    Updater.engine = "Github"
    Updater.private_token = None
    Updater.user = "Seris0"
    Updater.repo = "QuickImportXXMI"
    Updater.website = "https://github.com/Seris0/QuickImportXXMI/releases"
    Updater.subfolder_path = ""
    Updater.current_version = bl_info["version"]
    Updater.verbose = False
    Updater.backup_current = False
    Updater.backup_ignore_patterns = ["*"]
    Updater.overwrite_patterns = ["*"]
    Updater.remove_pre_update_patterns = ["*"]
    Updater.include_branches = False
    Updater.use_releases = False
    Updater.include_branch_list = None
    Updater.manual_only = False
    Updater.fake_install = False
    Updater.showpopups = True
    Updater.version_min_update = (1, 0, 0)
    Updater.version_max_update = None
    Updater.skip_tag = skip_tag_function
    Updater.select_link = select_link_function

    for cls in classes:
        make_annotations(cls)
        bpy.utils.register_class(cls)

    show_reload_popup()


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    Updater.clear_state()

    global ran_autocheck_install_popup
    ran_autocheck_install_popup = False

    global ran_update_sucess_popup
    ran_update_sucess_popup = False

    global ran_background_check
    ran_background_check = False