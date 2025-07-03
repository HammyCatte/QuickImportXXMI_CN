
import bpy #type: ignore
import os
from .modules.import_ops import QuickImportXXMIFrameAnalysis, QuickImport3DMigotoRaw
from .texturehandling import TextureHandler, TextureHandler42
from .preferences import *
import re

class QuickImportBase:
    def post_import_processing(self, context, folder):

        xxmi = context.scene.quick_import_settings
        imported_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']

        if xxmi.reset_rotation:
            self.reset_rotation(context)

        if xxmi.tri_to_quads:
            self.convert_to_quads()

        if xxmi.merge_by_distance:
            self.merge_by_distance()

        if xxmi.import_textures:
            self.setup_textures(context)

        if xxmi.create_collection:
            self.create_collection(context, folder)

        new_meshes = [obj for obj in imported_objects if obj.type == 'MESH']
        
        print(f"检测到新的网格对象: {[obj.name for obj in new_meshes]}")

        if xxmi.import_textures:
            self.assign_existing_materials(new_meshes)

        if xxmi.import_face:
            self.import_face(context)

        if xxmi.import_armature:
            self.import_armature(context)
            
        if xxmi.create_mesh_collection:
            self.create_mesh_collection(context, folder)
      
        bpy.ops.object.select_all(action='DESELECT')
        
    def assign_existing_materials(self, new_meshes):
        for obj in new_meshes:
            if not obj.material_slots:
                combined_name, letter = self.extract_combined_name(obj.name)
                print(f"从 {obj.name} 提取的组合名称: '{combined_name}'，字母后缀: '{letter}'")

                if combined_name:
                    matching_material = self.find_matching_material(combined_name, letter)
                    
                    # If still no material found and it's a Dress, try finding any Body material
                    if not matching_material and "Dress" in combined_name:
                        prefix = combined_name.split("Dress")[0]
                        for material in bpy.data.materials:
                            if material.name.startswith("mat_") and f"{prefix}Body".lower() in material.name.lower():
                                matching_material = material
                                print(f"为Dress使用通用的Body材质: {matching_material.name}")
                                break
                
                    if matching_material:
                        obj.data.materials.append(matching_material)
                        print(f"将材质 {matching_material.name} 分配给 {obj.name}")
                    else:
                        print(f"未找到与 {obj.name} 的组合名称 '{combined_name}' 匹配的材质")
                else:
                    print(f"{obj.name} 中未找到有效的组合名称以匹配材质")

    def extract_combined_name(self, name):
        keywords = ['Body', 'Head', 'Arm', 'Leg', 'Dress', 'Extra', 'Extras', 'Hair', 'Mask', 'Idle', 'Face']
        for keyword in keywords:
            if keyword.lower() in name.lower():
                # Find the actual keyword in the original case
                keyword_index = name.lower().find(keyword.lower())
                actual_keyword = name[keyword_index:keyword_index + len(keyword)]
                parts = name.split(actual_keyword)
                prefix = parts[0]
                letter = parts[1][0] if len(parts) > 1 and parts[1] else ''
                combined_name = prefix + actual_keyword
                print(f"从 '{prefix}' 和 '{keyword}' 生成的组合名称 '{combined_name}'，字母后缀: '{letter}'")
                return combined_name, letter
        print(f"{name} 中未匹配到关键字")
        return "", ""

    def find_matching_material(self, combined_name, letter):
        # 特殊规则：Asta 的材质映射
        if combined_name.lower() == "astabody":
            asta_material_mapping = {
                'C': 'BodyB',
                'D': 'BodyA',
                'E': 'BodyB'
            }
            target_material_suffix = asta_material_mapping.get(letter)
            if target_material_suffix:
                for material in bpy.data.materials:
                    if material.name.startswith("mat_") and target_material_suffix.lower() in material.name.lower():
                        print(f"根据字母后缀 '{letter}' 找到 Asta 规则材质 {material.name}")
                        return material
                print(f"未找到字母后缀 '{letter}' 对应的 Asta 规则材质")
            else:
                print(f"字母后缀 '{letter}' 不符合 Asta 规则要求")
            return None

        # 标准匹配逻辑：从字母后缀开始反向搜索
        letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        start_index = letters.index(letter) if letter in letters else -1

        for i in range(start_index, -1, -1):
            current_letter = letters[i] if i >= 0 else ''
            for material in bpy.data.materials:
                print(f"检查材质 {material.name} 是否匹配组合名称 '{combined_name}{current_letter}'")
                if material.name.startswith("mat_") and f"{combined_name}{current_letter}".lower() in material.name.lower():
                    return material

        return None
           
    def create_collection(self, context, folder):
        collection_name = os.path.basename(folder)
        new_collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(new_collection)

        for obj in bpy.context.selected_objects:
            if obj.users_collection:  
                for coll in obj.users_collection:
                    coll.objects.unlink(obj)
            new_collection.objects.link(obj)
            print(f"已将 {obj.name} 移至集合 {collection_name}")

    def create_mesh_collection(self, context, folder):
        #Sins logic for collections with custom properties, 
        # I will probably change this to don't use bmesh in futurec
        import bmesh #type: ignore
        collection_name = os.path.basename(folder)
        new_collection = bpy.data.collections.new(collection_name+"_CustomProperties")
        bpy.context.scene.collection.children.link(new_collection)
        new_collection.color_tag = "COLOR_08"

        selected_objects = [obj for obj in bpy.context.selected_objects]
        for obj in selected_objects:
            # Skip if object is an armature or in Face collection
            if obj.type == 'ARMATURE' or (obj.users_collection and 'Face' in [c.name for c in obj.users_collection]):
                print(f"跳过 {obj.name}，因为它是骨架或面部网格")
                continue

            if obj.name.startswith(collection_name):
                bpy.ops.object.mode_set(mode='OBJECT')
                bpy.context.scene.collection.objects.unlink(obj)
                new_collection.objects.link(obj)
                new_collection.hide_select = True

                try:
                    #duplicate data to new containers in collections
                    name = obj.name.split(collection_name)[1].rsplit("-", 1)[0]
                    new_sub_collection = bpy.data.collections.new(obj.name.rsplit("-", 1)[0])
                    bpy.context.scene.collection.children.link(new_sub_collection)
                    ob = bpy.data.objects.new(name = name, object_data = obj.data.copy())
                    ob.location = obj.location
                    ob.rotation_euler = obj.rotation_euler
                    ob.scale = obj.scale
                    new_sub_collection.objects.link(ob)

                    #Del verts of imported containers
                    if obj.type == 'MESH':
                        bm = bmesh.new()
                        bm.from_mesh(obj.data)
                        [bm.verts.remove(v) for v in bm.verts]
                        bm.to_mesh(obj.data)
                        obj.data.update()
                        bm.free()
                        print(f"已将 {obj.name} 作为 {ob.name} 移至集合 {name}")
                        obj.name = obj.name.rsplit("-", 1)[0] + "-KeepEmpty"
                        print(f"{obj.name} 保留自定义属性，请勿删除。")

                        # Move any existing armature modifiers from the empty to the new mesh
                        for mod in obj.modifiers:
                            if mod.type == 'ARMATURE':
                                new_mod = ob.modifiers.new(name="Armature", type='ARMATURE')
                                new_mod.object = mod.object
                                obj.modifiers.remove(mod)
                    else:
                        print(f"跳过非网格对象 {obj.name} 的顶点移除")

                except IndexError:
                    print(f"{obj.name} 失败，因为它不包含集合名称")
            else:
                print(f"忽略 {obj.name}，因为它与集合名称不匹配")

    def reset_rotation(self, context):
        for obj in context.selected_objects:
            if obj.name in [o.name for o in bpy.context.selected_objects]:
                obj.rotation_euler = (0, 0, 0)

    def convert_to_quads(self):
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.tris_convert_to_quads(uvs=True, vcols=True, seam=True, sharp=True, materials=True)
        bpy.ops.mesh.delete_loose()

    def merge_by_distance(self):
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles(use_sharp_edge_from_normals=True)
        bpy.ops.mesh.delete_loose()

    def setup_textures(self, context):
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.delete_loose()
        bpy.ops.object.mode_set(mode='OBJECT')
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.shading.type = 'MATERIAL'
        
        # if bpy.app.version >= (4, 2, 0):
        #     bpy.data.scenes["Scene"].view_settings.view_transform = 'Khronos PBR Neutral'

    def import_armature(self, context):
        try:
            # Step 1: Track the original selection
            previously_selected = set(bpy.context.selected_objects)

            # Step 2: Filter out invalid body objects (Head and Faces should have armatures on it)
            body_objects = [
                obj for obj in previously_selected
                if obj.type == 'MESH'
                and not any(col.name == 'Face' for col in obj.users_collection)
                and '-KeepEmpty' not in obj.name
                and not any(head in obj.name for head in ['HeadA', 'HeadB'])
            ]

            if not body_objects:
                raise Exception("未选择用于骨架导入的有效主体对象")

            # Step 3: Select the first body object as reference for armature import
            obj = body_objects[0]
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            context.view_layer.objects.active = obj

            # Step 4: Import the armature file
            original_selection = set(bpy.context.selected_objects)
            bpy.ops.import_scene.armature_file()
            newly_imported = set(bpy.context.selected_objects) - original_selection

            # Step 5: Identify all imported armatures
            imported_armatures = [obj for obj in newly_imported if obj.type == 'ARMATURE']
            if not imported_armatures:
                raise Exception("在导入的物体中未发现骨架")

            # Step 6: Match each mesh to the most appropriate armature
            for obj in body_objects:
                # Extract base name for matching
                obj_base_name = obj.name.split('-')[0].split('=')[0].lower()

                # Find the best matching armature dynamically
                best_match = None
                best_score = 0
                for armature in imported_armatures:
                    # Set armature scale based on flip_mesh setting
                    if context.scene.quick_import_settings.flip_mesh:
                        armature.scale = (1, 1, 1)
                    else:
                        armature.scale = (-1, 1, 1)
                        
                    armature_base = armature.name.replace('_', '').lower()
                    score = sum(1 for char in obj_base_name if char in armature_base)
                    if score > best_score:
                        best_match = armature
                        best_score = score

                if best_match:
                    # Check if armature modifier already exists
                    existing_mod = next((mod for mod in obj.modifiers if mod.type == 'ARMATURE'), None)
                    if existing_mod:
                        existing_mod.object = best_match
                    else:
                        mod = obj.modifiers.new(name="Armature", type='ARMATURE')
                        mod.object = best_match

            # Step 7: Restore selection to include newly imported objects and previously selected objects
            for obj in newly_imported:
                obj.select_set(True)
            for obj in previously_selected:
                if obj not in newly_imported:
                    obj.select_set(True)

        except Exception as e:
            self.report({'ERROR'}, f"骨架导入失败: {str(e)}")
            for obj in previously_selected:
                obj.select_set(True)

                
    def import_face(self, context):
        try:
            previously_selected = set(bpy.context.selected_objects)
            
            if previously_selected:
                obj = list(previously_selected)[0]
                bpy.ops.object.select_all(action='DESELECT')
                obj.select_set(True)
                context.view_layer.objects.active = obj
            
            bpy.ops.import_scene.face_file()
            newly_imported = set(bpy.context.selected_objects) - previously_selected
            
            if not newly_imported:
                raise Exception("未找到要导入的面部网格")
                
            face_collection = bpy.data.collections.new("Face")
            bpy.context.scene.collection.children.link(face_collection)
            
            # Move all imported meshes to Face collection
            for obj in newly_imported:
                # Remove from current collections
                for col in obj.users_collection:
                    col.objects.unlink(obj)   
                face_collection.objects.link(obj)
                obj.select_set(True)

            # Reselect original objects
            for obj in previously_selected:
                obj.select_set(True)
                
        except Exception as e:
            self.report({'ERROR'}, f"面部导入失败: {str(e)}")
            for obj in previously_selected:
                obj.select_set(True)


# Common name mappings and parts used across operators
CHARACTER_NAME_MAPPING = {
    "AratakiItto": "Itto",
    "Arataki": "Itto", 
    "TravelerBoy": "Aether",
    "TravelerMale": "Aether",
    "KamisatoAyaka": "Ayaka",
    "KamisatoAyato": "Ayato",
    "Raiden": "RaidenShogun",
    "Shogun": "RaidenShogun",
    "TravelerGirl": "Lumine",
    "TravelerFemale": "Lumine",
    "SangonomiyaKokomi": "Kokomi",
    "KaedeharaKazuha": "Kazuha",
    "Kaedehara": "Kazuha",
    "Yae": "YaeMiko",
    "FischlSkin": "FischlHighness",
    "NingguangSkin": "NingguangOrchid",
    "MonaGlobal": "Mona",
    "Tartaglia": "Childe",
    "BarbaraSkin": "BarbaraSummertime",
    "DilucSkin": "DilucFlamme",
    "DilucFlames": "DilucFlamme",
    "KiraraSkin": "KiraraBoots",
    "Kujou": "KujouSara",
    "Sara": "KujouSara",
    "Kuki": "Shinobu",
    "KukiShinobu": "Shinobu",
    "HutaoSkin": "HutaoCherry",
    "HutaoCherries": "HutaoCherry",
    "HutaoSnow": "HutaoCherry",
    "HutaoLaden": "HutaoCherry",
    "HutaoCherriesSnowLaden": "HutaoCherry",
    "HutaoCherriesSnow": "HutaoCherry",


    
    # "FurinaPonytail": "Furina"
}

COMMON_PARTS = ['PonyTail', 'Body', 'Head', 'Arm', 'Leg', 'Dress', 'Extra', 'Extras', 'Hair', 'Mask', 'Idle', 'Eyes', 'Coat', 'JacketHead', 'JacketBody', 'Jacket',
'Hat', 'HatHead', 'HatBody']


class QuickImportArmature(bpy.types.Operator):
    bl_idname = "import_scene.armature_file"
    bl_label = "导入骨架" 
    bl_description = "导入匹配的骨架文件"
    
    def execute(self, context):
        try:
            self.post_import_processing(context)
        except FileNotFoundError as e:
            self.report({'ERROR'}, f"文件未找到: {str(e)}")
            return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        return {'FINISHED'}
    
    def post_import_processing(self, context):
        script_dir = os.path.dirname(os.path.realpath(__file__))
        print(f"脚本目录: {script_dir}")
        base_armatures_dir = os.path.join(script_dir, "resources", "armatures")
        print(f"基础骨架目录: {base_armatures_dir}")
        
        if not os.path.exists(base_armatures_dir):
            raise FileNotFoundError(f"骨架目录不存在: {base_armatures_dir}")
        
        # Define game-specific armature directories
        gi_armatures_dir = os.path.join(base_armatures_dir, "GI")
        hsr_armatures_dir = os.path.join(base_armatures_dir, "HSR")
        
        selected_objects = context.selected_objects
        if not selected_objects:
            raise Exception("未选择任何对象")

        # Group objects by their base name before any common parts
        object_groups = {}
        for obj in selected_objects:
            obj_name = obj.name.split('-')[0].split('=')[0]
            if not obj_name:
                continue

            # Sort COMMON_PARTS by length in descending order to match longest parts first
            sorted_parts = sorted(COMMON_PARTS, key=len, reverse=True)
            
            # Try to find any common parts in the name
            base_name = obj_name
            found_part = False
            for part in sorted_parts:
                if part.lower() in obj_name.lower():
                    # Get everything before the part
                    base_name = re.split(part, obj_name, flags=re.IGNORECASE)[0]
                    found_part = True
                    break
            
            # Only add objects that have a recognized part to the main group
            if found_part:
                base_name = CHARACTER_NAME_MAPPING.get(base_name, base_name)
                if base_name not in object_groups:
                    object_groups[base_name] = []
                object_groups[base_name].append(obj)
            else:
                print(f"跳过具有无法识别部分的对象: {obj.name}")

        # Don't try to import armature for Face collection
        if "Face" in object_groups:
            return {'FINISHED'}

        # Process each group separately
        for base_name, objects in object_groups.items():
            if not base_name:
                continue

            # Search in both GI and HSR directories
            armature_found = False
            for armatures_dir in [gi_armatures_dir, hsr_armatures_dir]:
                if not os.path.exists(armatures_dir):
                    continue
                    
                # Find files that match the base name up until "Armature" and end with .blend
                matching_files = [
                    f for f in os.listdir(armatures_dir)
                    if f.endswith('.blend') 
                    and (armature_idx := f.lower().find('armature')) != -1
                    and f[:armature_idx].lower() == base_name.lower()
                ]
                
                if matching_files:
                    armature_path = os.path.join(armatures_dir, matching_files[0])
                    
                    with bpy.data.libraries.load(armature_path) as (data_from, data_to):
                        armature_objects = [name for name in data_from.objects if 'Armature' in name]
                        if not armature_objects:
                            print(f"警告：文件中未找到骨架: {armature_path}")
                            continue
                        data_to.objects = armature_objects
              
                    for obj in data_to.objects:
                        if obj is not None:
                            context.scene.collection.objects.link(obj)
                            obj.select_set(True)
                            armature_found = True
                    break  # Stop searching if armature was found
                    
            if not armature_found:
                print(f"警告：在 GI 或 HSR 目录中未找到与 {base_name} 匹配的骨架文件")


class QuickImportRaw(QuickImport3DMigotoRaw, QuickImportBase):
    """导入角色的原始数据(.IB + .VB)文件"""
    bl_idname = "import_scene.3dmigoto_raw"
    bl_label = "XXMI原始数据导入"
    bl_options = {"UNDO"}

    def execute(self, context):
        result = super().execute(context)
        if result != {"FINISHED"}:
            return result
        
        folder = os.path.dirname(self.properties.filepath)
        print("------------------------")

        print(f"找到目录: {folder}")
        files = os.listdir(folder)
        files = [f for f in files if f.endswith("Diffuse.dds")]
        print(f"文件列表: {files}")

        if bpy.app.version < (4, 2, 0):
            importedmeshes = TextureHandler.create_material(context, files, folder)
        else:
            importedmeshes = TextureHandler42.create_material(context, files, folder)

        print(f"已导入网格对象: {[obj.name for obj in importedmeshes]}")

        self.post_import_processing(context, folder)

        return {"FINISHED"}
                   
class QuickImportFace(bpy.types.Operator):
    bl_idname = "import_scene.face_file"
    bl_label = "导入面部"
    bl_description = "导入匹配的面部文件"
    
    # 面部特殊名称映射
    FACE_NAME_MAPPING = {
        "JeanCN": "Jean",
        "JeanSea": "Jean", 
        "JeanSkin": "Jean",
        "KaeyaSailwind": "Kaeya",
        "KeQingSkin": "Keqing",
        "KeQingOpulent": "Keqing",
        "KeQingOpulentSplendor": "Keqing",
        "ShenheFrostFlower": "Shenhe",
        "ShenheFlower": "Shenhe"
    }
    
    def execute(self, context):
        try:
            self.post_import_processing(context)
        except FileNotFoundError as e:
            self.report({'ERROR'}, f"文件未找到: {str(e)}")
            return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        return {'FINISHED'}
    
    def post_import_processing(self, context):
        script_dir = os.path.dirname(os.path.realpath(__file__))
        faces_dir = os.path.join(script_dir, "resources", "faces")
        
        if not os.path.exists(faces_dir):
            raise FileNotFoundError(f"面部目录不存在: {faces_dir}")
        
        selected_objects = context.selected_objects
        if not selected_objects:
            raise Exception("未选择任何对象")
        
        obj_name = selected_objects[0].name.split('-')[0].split('=')[0]
        if not obj_name:
            raise Exception("无效的对象名称")
        
        # Sort COMMON_PARTS by length in descending order to match longest parts first
        sorted_parts = sorted(COMMON_PARTS, key=len, reverse=True)
        
        # First try to find any common parts in the name
        base_name = obj_name
        for part in sorted_parts:
            if part.lower() in obj_name.lower():
                # Get everything before the part
                base_name = re.split(part, obj_name, flags=re.IGNORECASE)[0]
                break
        
        # First check face-specific mappings, then fall back to general mappings
        base_name = self.FACE_NAME_MAPPING.get(base_name, CHARACTER_NAME_MAPPING.get(base_name, base_name))
        
        if not base_name:
            raise Exception("无法确定基本名称")
        
        matching_files = [f for f in os.listdir(faces_dir) 
                          if base_name.lower() in f.lower() and f.endswith('.blend')]
        
        if not matching_files:
            raise FileNotFoundError(f"在 {faces_dir} 中未找到与 {base_name} 匹配的面部文件")
        
        face_path = os.path.join(faces_dir, matching_files[0])
        if not os.path.isfile(face_path):
            raise FileNotFoundError(f"未找到面部文件: {face_path}")
            
        with bpy.data.libraries.load(face_path) as (data_from, data_to):
            data_to.objects = [name for name in data_from.objects]
      
        for obj in data_to.objects:
            if obj is not None:
                context.scene.collection.objects.link(obj)
                obj.select_set(True)

class QuickImport(QuickImportXXMIFrameAnalysis, QuickImportBase):
    """导入角色的帧分析数据(.txt)文件"""
    bl_idname = "import_scene.3dmigoto_frame_analysis"
    bl_label = "XXMI快速导入"
    bl_options = {"UNDO"}

    def execute(self, context):
        cfg = context.scene.quick_import_settings
        self.flip_mesh = cfg.flip_mesh
        super().execute(context)

        folder = os.path.dirname(self.properties.filepath)
        print(f"找到目录: {folder}")

        files = os.listdir(folder)
        print (f"文件列表: {files}")

        texture_files = []
        if cfg.import_textures:
            texture_map = {
                "Diffuse": cfg.import_diffuse,
                "DiffuseUlt" : cfg.import_diffuse,
                "NormalMap": cfg.import_normalmap,
                "LightMap": cfg.import_lightmap,
                "StockingMap": cfg.import_stockingmap,
                "MaterialMap": cfg.import_materialmap
                # if cfg.game == 'HSR' else False,
            }

            for texture_type, should_import in texture_map.items():
                if should_import:
                    texture_files.extend([f for f in files if f.lower().endswith(f"{texture_type.lower()}.dds")])
            print(f"待导入贴图文件: {texture_files}")
        if bpy.app.version < (4, 2, 0):
            importedmeshes = TextureHandler.create_material(context, texture_files, folder)
        else:
            importedmeshes = TextureHandler42.create_material(context, texture_files, folder)

        print(f"已导入网格对象: {[obj.name for obj in importedmeshes]}")

        self.post_import_processing(context, folder)

        return {"FINISHED"}
    
class SavePreferencesOperator(bpy.types.Operator):
    bl_idname = "quickimport.save_preferences"
    bl_label = "保存导入设置"
    bl_description = "将当前快速导入设置保存为默认偏好设置"
    
    def execute(self, context):
        save_preferences(context)
        self.report({'INFO'}, "偏好设置保存成功！")
        return {'FINISHED'}
       
def menu_func_import(self, context):
    self.layout.operator(QuickImport.bl_idname, text="XXMI快速导入")   
    self.layout.operator(QuickImportRaw.bl_idname, text="XXMI原始数据导入")


