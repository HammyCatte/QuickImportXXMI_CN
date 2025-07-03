import bpy
from bpy.props import BoolProperty, IntProperty, StringProperty
from bpy.types import Operator, AddonPreferences
from bpy_extras.io_utils import ImportHelper, orientation_helper

from .. import __name__ as package_name
from .. import addon_updater_ops # type: ignore
from .datahandling import (
    Fatal,
    apply_vgmap,
    import_pose,
    merge_armatures,
    update_vgmap,
)

from .datastructures import IOOBJOrientationHelper


class ApplyVGMap(Operator, ImportHelper):
    """将顶点组映射应用于选定对象"""

    bl_idname = "mesh.migoto_vertex_group_map"
    bl_label = "应用 3DMigoto vgmap"
    bl_options = {"UNDO"}

    filename_ext = ".vgmap"
    filter_glob: StringProperty(
        default="*.vgmap",
        options={"HIDDEN"},
    ) # type: ignore

    # commit: BoolProperty(
    #        name="Commit to current mesh",
    #        description="Directly alters the vertex groups of the current mesh, rather than performing the mapping at export time",
    #        default=False,
    #        )

    rename: BoolProperty(
        name="重命名现有顶点组",
        description="重命名现有的顶点组以匹配 vgmap 文件",
        default=True,
    ) # type: ignore

    cleanup: BoolProperty(
        name="删除未列出的顶点组",
        description="删除 vgmap 文件中未列出的任何现有顶点组",
        default=False,
    ) # type: ignore

    reverse: BoolProperty(
        name="交换源和目标",
        description="反转顶点组映射顺序 - 若当前网格是目标且需使用来源('from')骨骼时启用此选项'",
        default=False,
    ) # type: ignore

    suffix: StringProperty(
        name="Suffix",
        description="Suffix to add to the vertex buffer filename when exporting, for bulk exports of a single mesh with multiple distinct vertex group maps",
        default="",
    ) # type: ignore

    def invoke(self, context, event):
        self.suffix = ""
        return ImportHelper.invoke(self, context, event)

    def execute(self, context):
        try:
            keywords = self.as_keywords(ignore=("filter_glob",))
            apply_vgmap(self, context, **keywords)
        except Fatal as e:
            self.report({"ERROR"}, str(e))
        return {"FINISHED"}


class UpdateVGMap(Operator):
    """分配新的 3DMigoto 顶点组"""

    bl_idname = "mesh.update_migoto_vertex_group_map"
    bl_label = "分配新的 3DMigoto 顶点组"
    bl_options = {"UNDO"}

    vg_step: bpy.props.IntProperty(
        name="顶点组步长",
        description="如果使用的顶点组是 0、1、2、3 等，则指定 1。如果它们是 0、3、6、9、12 等，则指定 3",
        default=1,
        min=1,
    ) # type: ignore

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context):
        try:
            keywords = self.as_keywords()
            update_vgmap(self, context, **keywords)
        except Fatal as e:
            self.report({"ERROR"}, str(e))
        return {"FINISHED"}


@orientation_helper(axis_forward="-Z", axis_up="Y")
class Import3DMigotoPose(Operator, ImportHelper, IOOBJOrientationHelper):
    """从 3DMigoto 常量缓冲区转储导入姿势"""

    bl_idname = "armature.migoto_pose"
    bl_label = "导入 3DMigoto 姿势"
    bl_options = {"UNDO"}

    filename_ext = ".txt"
    filter_glob: StringProperty(
        default="*.txt",
        options={"HIDDEN"},
    ) # type: ignore

    limit_bones_to_vertex_groups: BoolProperty(
        name="将骨骼限制到顶点组",
        description="将导入的骨骼的最大数量限制为活动对象的顶点组数量",
        default=True,
    ) # type: ignore

    pose_cb_off: bpy.props.IntVectorProperty(
        name="骨骼CB（常量缓冲区）范围",
        description="指定在骨骼常量缓冲区中查找矩阵的起始/结束偏移量（按4分量值的倍数计算）",
        default=[0, 0],
        size=2,
        min=0,
    ) # type: ignore

    pose_cb_step: bpy.props.IntProperty(
        name="顶点组步长",
        description="如果使用的顶点组是 0、1、2、3 等，则指定 1。如果它们是 0、3、6、9、12 等，则指定 3",
        default=1,
        min=1,
    ) # type: ignore

    def execute(self, context):
        try:
            keywords = self.as_keywords(ignore=("filter_glob",))
            import_pose(self, context, **keywords)
        except Fatal as e:
            self.report({"ERROR"}, str(e))
        return {"FINISHED"}


class Merge3DMigotoPose(Operator):
    """将相关骨架的相同姿势的骨骼合并为一个"""

    bl_idname = "armature.merge_pose"
    bl_label = "合并 3DMigoto 姿势"
    bl_options = {"UNDO"}

    def execute(self, context):
        try:
            merge_armatures(self, context)
        except Fatal as e:
            self.report({"ERROR"}, str(e))
        return {"FINISHED"}


class DeleteNonNumericVertexGroups(Operator):
    """删除具有非数字名称的顶点组"""

    bl_idname = "vertex_groups.delete_non_numeric"
    bl_label = "删除非数字顶点组"
    bl_options = {"UNDO"}

    def execute(self, context):
        try:
            for obj in context.selected_objects:
                for vg in reversed(obj.vertex_groups):
                    if vg.name.isdecimal():
                        continue
                    print("Removing vertex group", vg.name)
                    obj.vertex_groups.remove(vg)
        except Fatal as e:
            self.report({"ERROR"}, str(e))
        return {"FINISHED"}


class Preferences(AddonPreferences):
    """偏好设置更新程序"""

    bl_idname = package_name
    # 插件更新程序偏好设置。

    auto_check_update: BoolProperty(
        name="自动检查更新",
        description="如果启用，则使用间隔自动检查更新",
        default=False,
    ) # type: ignore

    updater_interval_months: IntProperty(
        name="月数",
        description="检查更新的间隔月数",
        default=0,
        min=0,
    ) # type: ignore

    updater_interval_days: IntProperty(
        name="天数",
        description="检查更新的间隔天数",
        default=7,
        min=0,
        max=31,
    ) # type: ignore

    updater_interval_hours: IntProperty(
        name="小时",
        description="检查更新的间隔小时",
        default=0,
        min=0,
        max=23,
    ) # type: ignore

    updater_interval_minutes: IntProperty(
        name="分钟",
        description="检查更新的间隔分钟",
        default=0,
        min=0,
        max=59,
    ) # type: ignore

    def draw(self, context):
        layout = self.layout
        print(addon_updater_ops.get_user_preferences(context))
        # 如果是一列，或者只是 self.layout，则效果最佳。
        mainrow = layout.row()
        _ = mainrow.column()
        # 更新程序绘制函数，也可以传入 col 作为第三个参数。
        addon_updater_ops.update_settings_ui(self, context)

        # 替代性绘制函数（紧凑版），可嵌入现有绘制函数内，仅包含：
        #   1) 检查更新/立即更新按钮
        #   2) 自动检查开关（间隔时间与上方设置相同）
        # addon_updater_ops.update_settings_ui_condensed(self, context, col)

        # 添加辅助列以单列形式显示上述紧凑UI
        # col = mainrow.column()
        # col.scale_y = 2
        # ops = col.operator("wm.url_open", "打开网页")
        # ops.url=addon_updater_ops.updater.website
