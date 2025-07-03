 
import bpy #type: ignore
import os
from . import bl_info
from bpy.props import PointerProperty, StringProperty, EnumProperty, BoolProperty #type: ignore 
from .tools.tools_operators import *
from . import addon_updater_ops

class XXMI_TOOLS_PT_main_panel(bpy.types.Panel):
    bl_label = "XXMI工具箱"
    bl_idname = "XXMI_TOOLS_PT_MainPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'XXMI工具箱'
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        xxmi = context.scene.xxmi_scripts_settings
        

        # GitHub链接和版本信息
        box = layout.box()
        github_row = box.row(align=True)
        github_row.label(text=f"XXMI工具箱 & 快速导入 | 当前版本: v{'.'.join(map(str, bl_info['version']))}", icon='INFO')
        github_row.alignment = 'EXPAND'
        github_row.operator("wm.url_open", text="", icon='URL', emboss=False).url = "https://github.com/Seris0/Gustav0/tree/main/Addons/QuickImportXXMI"

        # 主工具模块
        box = layout.box()
        row = box.row()
        row.prop(xxmi, "show_vertex", icon="TRIA_DOWN" if xxmi.show_vertex else "TRIA_RIGHT", emboss=False, text="主工具")
        if xxmi.show_vertex:
            col = box.column(align=True)
            col.label(text="顶点组管理", icon='GROUP_VERTEX')
            col.prop(xxmi, "Largest_VG", text="最大顶点组")
            col.operator("XXMI_TOOLS.fill_vgs", text="填充顶点组", icon='ADD')
            col.operator("XXMI_TOOLS.remove_unused_vgs", text="移除未使用顶点组", icon='X')
            col.operator("XXMI_TOOLS.remove_all_vgs", text="清除所有顶点组", icon='CANCEL')
            col.operator("object.separate_by_material_and_rename", text="按材质分离", icon='MATERIAL')

            col.separator()
            col.label(text="合并顶点组", icon='AUTOMERGE_ON')
            col.prop(xxmi, "merge_mode", text="")
            if xxmi.merge_mode == 'MODE1':
                col.prop(xxmi, "vertex_groups", text="顶点组列表")
            elif xxmi.merge_mode == 'MODE2':
                row = col.row(align=True)
                row.prop(xxmi, "smallest_group_number", text="起始编号")
                row.prop(xxmi, "largest_group_number", text="结束编号")
            col.operator("object.merge_vertex_groups", text="执行合并")

        # 顶点组重映射模块
        box = layout.box()
        row = box.row()
        row.prop(xxmi, "show_remap", icon="TRIA_DOWN" if xxmi.show_remap else "TRIA_RIGHT", emboss=False, text="顶点组重映射")
        if xxmi.show_remap:
            col = box.column(align=True)
            col.prop_search(xxmi, "vgm_source_object", bpy.data, "objects", text="源对象")
            col.separator()
            col.prop_search(xxmi, "vgm_destination_object", bpy.data, "objects", text="目标对象")
            col.separator()
            col.operator("object.vertex_group_remap", text="执行重映射", icon='FILE_REFRESH')

        # 属性转移模块
        box = layout.box()
        box.prop(xxmi, "show_transfer", icon="TRIA_DOWN" if xxmi.show_transfer else "TRIA_RIGHT", emboss=False, text="属性转移")
        if xxmi.show_transfer:
            box.label(text="跨对象属性同步", icon='OUTLINER_OB_GROUP_INSTANCE')  
            row = box.row()
            row.prop(xxmi, "transfer_mode", text="转移模式")
            if xxmi.transfer_mode == 'COLLECTION':
                row = box.row()
                row.prop_search(xxmi, "base_collection", bpy.data, "collections", text="原始属性")
                row = box.row()
                row.prop_search(xxmi, "target_collection", bpy.data, "collections", text="缺失属性")
            else:
                row = box.row()
                row.prop_search(xxmi, "base_objectproperties", bpy.data, "objects", text="源对象")
                row = box.row()
                row.prop_search(xxmi, "target_objectproperties", bpy.data, "objects", text="目标对象")
            row = box.row()
            row.operator("object.transfer_properties", text="执行属性转移", icon='OUTLINER_OB_GROUP_INSTANCE')

class XXMI_Scripts_Settings(bpy.types.PropertyGroup):
    show_vertex: bpy.props.BoolProperty(name="显示顶点工具", default=False) #type: ignore        
    show_remap: bpy.props.BoolProperty(name="显示重映射", default=False) #type: ignore
    show_transfer: bpy.props.BoolProperty(name="显示属性转移", default=False) #type: ignore
    base_collection: bpy.props.PointerProperty(type=bpy.types.Collection, description="原始集合") #type: ignore
    target_collection: bpy.props.PointerProperty(type=bpy.types.Collection, description="目标集合") #type: ignore
    base_objectproperties: bpy.props.PointerProperty(type=bpy.types.Object, description="源对象") #type: ignore
    target_objectproperties: bpy.props.PointerProperty(type=bpy.types.Object, description="目标对象") #type: ignore    
    transfer_mode: bpy.props.EnumProperty(
        items=[
            ('COLLECTION', '集合间转移', '在集合之间转移属性'),
            ('MESH', '网格间转移', '在网格对象之间转移属性')
        ],
        default='MESH',
        description="属性转移模式"
    ) #type: ignore
    Largest_VG: bpy.props.IntProperty(description="最大顶点组数值") #type: ignore
    vgm_source_object: bpy.props.PointerProperty(type=bpy.types.Object, description="顶点组映射源对象") #type: ignore
    vgm_destination_object: bpy.props.PointerProperty(type=bpy.types.Object, description="顶点组映射目标对象") #type: ignore   
    merge_mode: bpy.props.EnumProperty(items=[
        ('MODE1', '模式1：指定顶点组', '合并特定顶点组'),
        ('MODE2', '模式2：编号范围', '按编号范围合并顶点组'),
        ('MODE3', '模式3：全部合并', '合并所有顶点组')], #type: ignore
        default='MODE3',
        description="顶点组合并模式") #type: ignore
    vertex_groups: bpy.props.StringProperty(name="顶点组列表", default="") #type: ignore
    smallest_group_number: bpy.props.IntProperty(name="最小组编号", default=0) #type: ignore
    largest_group_number: bpy.props.IntProperty(name="最大组编号", default=999) #type: ignore

class QuickImportSettings(bpy.types.PropertyGroup):
    tri_to_quads: BoolProperty(
        name="三角面转四边面",
        default=False,
        description="启用三角面转四边面功能"
    )#type: ignore 
    merge_by_distance: BoolProperty(
        name="顶点按距离合并",
        default=False,
        description="启用顶点自动按距离合并"
    )#type: ignore 
    flip_mesh: BoolProperty(
        name="Flip Mesh",
        default=False,
        description="Flips mesh over x-axis on import"
    ) #type: ignore 
    reset_rotation: BoolProperty(
        name="重置旋转(ZZZ)",
        default=False,
        description="导入时重置物体旋转"
    ) #type: ignore 
    import_textures: BoolProperty(
        name="导入贴图",
        default=True,
        description="自动应用材质和贴图"
    ) #type: ignore
    hide_textures: BoolProperty(
        name="隐藏贴图",
        default=False,
        description="隐藏贴图显示"
    ) #type: ignore
    
    def update_collection_settings(self, context):
        if self.create_mesh_collection:
            self.create_collection = False
        elif self.create_collection:
            self.create_mesh_collection = False
        
    def update_create_collection(self, context):
        if self.create_collection:
            self.create_mesh_collection = False

    def update_create_mesh_collection(self, context):
        if self.create_mesh_collection:
            self.create_collection = False

    create_collection: BoolProperty(
        name="创建集合",
        default=True,
        description="根据文件夹名称创建新集合",
        update=update_create_collection
    ) #type: ignore
    create_mesh_collection: BoolProperty(
        name="创建网格集合",
        default=False,
        description="为网格数据和自定义属性创建新集合",
        update=update_create_mesh_collection
    ) #type: ignore
    import_diffuse: BoolProperty(
        name="Diffuse",
        default=True,
        description="导入Diffuse贴图"
    ) #type: ignore 
    import_lightmap: BoolProperty(
        name="LightMap",
        default=False,
        description="导入LightMap贴图"
    ) #type: ignore 
    import_normalmap: BoolProperty(
        name="NormalMap",
        default=False,
        description="导入NormalMap贴图"
    ) #type: ignore 
    import_materialmap: BoolProperty(
        name="MaterialMap",
        default=False,
        description="导入MaterialMap贴图"
    ) #type: ignore 
    import_stockingmap: BoolProperty(
        name="StockingMap",
        default=False,
        description="导入StockingMap贴图"
    )  # type: ignore

    import_face: BoolProperty(
        name="自动导入面部",
        default=False,
        description="自动导入匹配的面部文件"
    ) #type: ignore
    import_armature: BoolProperty(
        name="自动导入骨架",
        default=False,
        description="自动导入匹配的骨架文件"
    ) #type: ignore
    hide_advanced: BoolProperty(
        name="隐藏高级设置",
        default=False,
        description="隐藏高级设置选项"
    ) #type: ignore

class XXMI_TOOLS_PT_quick_import_panel(bpy.types.Panel):
    bl_label = "快速导入"
    bl_idname = "XXMI_TOOLS_PT_QuickImportPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'XXMI工具箱'
 


    def draw_header(self, context):
        layout = self.layout
        row = layout.row()
        row.alignment = 'RIGHT'
        row.label(text="v"+".".join(str(i) for i in bl_info.get('version', (0, 0, 0))))

    def draw(self, context):
        layout = self.layout
        cfg = context.scene.quick_import_settings

        box = layout.box()
        col = box.column(align=True)
        
        row = col.row(align=True)
        row.scale_y = 1.3
        row.operator("import_scene.3dmigoto_frame_analysis", text="导入帧分析提取模型", icon='IMPORT')
        row = col.row(align=True)
        row.scale_y = 1.3
        row.operator("import_scene.3dmigoto_raw", text="导入原始缓冲区模型(ib + vb)", icon='IMPORT')
        
        col.separator()
        col.label(text="导入选项:", icon='SETTINGS')
        row = col.row(align=True)
        row.prop(cfg, "import_textures", toggle=True)
        row.prop(cfg, "merge_by_distance", toggle=True)
        
        row = col.row(align=True)
        row.prop(cfg, "reset_rotation", toggle=True)
        row.prop(cfg, "tri_to_quads", toggle=True)
        
        col.prop(cfg, "create_collection", toggle=True)
        col.prop(cfg, "create_mesh_collection", toggle=True)

        # 高级导入模块
        col.separator()
        row = col.row(align=True)
        row.label(text="高级导入:", icon='FACE_MAPS')
        row.prop(cfg, "hide_advanced", text="显示高级导入" if cfg.hide_advanced else "隐藏高级导入", 
                 icon='HIDE_OFF' if cfg.hide_advanced else 'HIDE_ON', toggle=True)
        
        if cfg.hide_advanced:
            col.separator()
            row = col.row()
            row.prop(cfg, "flip_mesh", toggle=True)
            col.separator()
            row = col.row()
            row.prop(cfg, "import_armature", toggle=True)
            row.prop(cfg, "import_face", toggle=True)

        if cfg.import_textures:
            col.separator()
            row = col.row(align=True)
            row.label(text="贴图导入:", icon='TEXTURE')
            row.prop(cfg, "hide_textures", text="显示贴图设置" if cfg.hide_textures else "隐藏贴图设置",
                     icon='HIDE_OFF' if cfg.hide_textures else 'HIDE_ON', toggle=True)
            
            if cfg.hide_textures:
                row = col.row(align=True)
                row.prop(cfg, "import_diffuse", toggle=True)
                row = col.row(align=True)
                row.prop(cfg, "import_lightmap", toggle=True)
                row.prop(cfg, "import_normalmap", toggle=True)
                row = col.row(align=True)
                row.prop(cfg, "import_materialmap", toggle=True)
                row.prop(cfg, "import_stockingmap", toggle=True)
                col.separator()

        col.separator()
        row = col.row(align=True)
        row.scale_y = 1.2
        row.operator("quickimport.save_preferences", text="保存偏好设置", icon='FILE_TICK')

class DemoUpdaterPanel(bpy.types.Panel):
	"""用于演示弹出通知及忽略功能的面板"""
	bl_label = "自动更新"
	bl_idname = "OBJECT_PT_DemoUpdaterPanel_hello"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'TOOLS' if bpy.app.version < (2, 80) else 'UI'
	bl_context = "objectmode"
	bl_category = "XXMI工具箱"
	bl_options = {'DEFAULT_CLOSED'}

	def draw(self, context: bpy.types.Context) -> None:
		addon_updater_ops.update_notice_box_ui(self, context)
		addon_updater_ops.update_settings_ui(self, context)


@addon_updater_ops.make_annotations
class UpdaterPreferences(bpy.types.AddonPreferences):
	"""基础插件更新偏好设置"""
	bl_idname = __package__

	# 插件更新器偏好设置

	auto_check_update = bpy.props.BoolProperty(
		name="自动检查更新",
		description="启用后，将按设定间隔自动检查更新",
		default=False)

	updater_interval_months = bpy.props.IntProperty(
		name='月数',
		description="检查更新间隔的月数",
		default=0,
		min=0)

	updater_interval_days = bpy.props.IntProperty(
		name='天数',
		description="检查更新间隔的天数",
		default=7,
		min=0,
		max=31)

	updater_interval_hours = bpy.props.IntProperty(
		name='小时',
		description="检查更新间隔的小时数",
		default=0,
		min=0,
		max=23)

	updater_interval_minutes = bpy.props.IntProperty(
		name='分钟',
		description="检查更新间隔的分钟数",
		default=0,
		min=0,
		max=59)

	def draw(self, context: bpy.types.Context) -> None:
		addon_updater_ops.update_settings_ui(self, context)
# 	def draw(self, context):
# 		layout = self.layout

# 		# Works best if a column, or even just self.layout.
# 		mainrow = layout.row()
# 		col = mainrow.column()

# 		# Updater draw function, could also pass in col as third arg.
# 		addon_updater_ops.update_settings_ui(self, context)

# 		# Alternate draw function, which is more condensed and can be
# 		# placed within an existing draw function. Only contains:
# 		#   1) check for update/update now buttons
# 		#   2) toggle for auto-check (interval will be equal to what is set above)
# 		# addon_updater_ops.update_settings_ui_condensed(self, context, col)

# 		# Adding another column to help show the above condensed ui as one column
# 		# col = mainrow.column()
# 		# col.scale_y = 2
# 		# ops = col.operator("wm.url_open","Open webpage ")
# 		# ops.url=addon_updater_ops.updater.website