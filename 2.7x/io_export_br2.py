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

bl_info = {
    "name": "Export Nexus Buddy 2(.br2)",
    "author": "Deliverator",
    "version": (1, 0),
    "blender": (2, 71, 0),
    "location": "File > Export > Nexus Buddy 2 (.br2)",
    "description": "Export Nexus Buddy 2 (.br2)",
    "warning": "",
    "wiki_url": "",
    "category": "Import-Export"}

import bpy
from bpy.props import BoolProperty, IntProperty, EnumProperty, StringProperty
import mathutils
from mathutils import Vector, Quaternion, Matrix
from bpy_extras.io_utils import unpack_list, unpack_face_list, ExportHelper
from os import remove

import time
import math
import struct
import re

def getTranslationOrientation(ob, file):
	if isinstance(ob, bpy.types.Bone):
		
		ob_matrix_local = ob.matrix_local.copy()
		ob_matrix_local.transpose()
		t = ob_matrix_local
		ob_matrix_local = Matrix([[-t[2][0], -t[2][1], -t[2][2], -t[2][3]],
								[t[1][0], t[1][1], t[1][2], t[1][3]],
								[t[0][0], t[0][1], t[0][2], t[0][3]],
								[t[3][0], t[3][1], t[3][2], t[3][3]]])
								
		rotMatrix_z90_4x4 = Matrix.Rotation(math.radians(90.0), 4, 'Z')
		rotMatrix_z90_4x4.transpose()
		
		file.write('Name:%s\n' % ob.name)

		t = rotMatrix_z90_4x4 * ob_matrix_local
		matrix = Matrix([[t[0][0], t[0][1], t[0][2], t[0][3]],
								[t[1][0], t[1][1], t[1][2], t[1][3]],
								[t[2][0], t[2][1], t[2][2], t[2][3]],
								[t[3][0], t[3][1], t[3][2], t[3][3]]])
								
		parent = ob.parent
		if parent:
			parent_matrix_local = parent.matrix_local.copy()
			parent_matrix_local.transpose()
			t = parent_matrix_local
			parent_matrix_local = Matrix([[-t[2][0], -t[2][1], -t[2][2], -t[2][3]],
									[t[1][0], t[1][1], t[1][2], t[1][3]],
									[t[0][0], t[0][1], t[0][2], t[0][3]],
									[t[3][0], t[3][1], t[3][2], t[3][3]]])
			par_matrix = rotMatrix_z90_4x4 * parent_matrix_local
			par_matrix_cpy = par_matrix.copy()
			par_matrix_cpy.invert()
			matrix = matrix * par_matrix_cpy

		matrix.transpose()
		loc, rot, sca = matrix.decompose()
	else:
		matrix = ob.matrix_world
		if matrix:
			loc, rot, sca = matrix.decompose()
		else:
			raise "error: this should never happen!"
	return loc, rot

def getBoneTreeDepth(bone, currentCount):
	if (bone.parent):
		currentCount = currentCount + 1
		return getBoneTreeDepth(bone.parent, currentCount)
	else:
		return currentCount
		
	
def BPyMesh_meshWeight2List(ob, me):
    """ Takes a mesh and return its group names and a list of lists, one list per vertex.
    aligning the each vert list with the group names, each list contains float value for the weight.
    These 2 lists can be modified and then used with list2MeshWeight to apply the changes.
    """

    # Clear the vert group.
    groupNames = [g.name for g in ob.vertex_groups]
    len_groupNames = len(groupNames)

    if not len_groupNames:
        # no verts? return a vert aligned empty list
        return [[] for i in range(len(me.vertices))], []
    else:
        vWeightList = [[0.0] * len_groupNames for i in range(len(me.vertices))]

    for i, v in enumerate(me.vertices):
        for g in v.groups:
            # possible weights are out of range
            index = g.group
            if index < len_groupNames:
                vWeightList[i][index] = g.weight

    return groupNames, vWeightList


def meshNormalizedWeights(ob, me):
    groupNames, vWeightList = BPyMesh_meshWeight2List(ob, me)

    if not groupNames:
        return [], []

    for i, vWeights in enumerate(vWeightList):
        tot = 0.0
        for w in vWeights:
            tot += w

        if tot:
            for j, w in enumerate(vWeights):
                vWeights[j] = w / tot

    return groupNames, vWeightList

def getBoneWeights(boneName, weights):
	if boneName in weights[0]:
		group_index = weights[0].index(boneName)
		vgroup_data = [(j, weight[group_index]) for j, weight in enumerate(weights[1]) if weight[group_index]] 
	else:
		vgroup_data = []
	
	return vgroup_data

def do_export(context,  filename):
	print ("Start BR2 Export...")
	file = open( filename, 'w')
	
	scene = context.scene
	
	filedata = "// Nexus Buddy BR2 - Exported from Blender for import to Nexus Buddy 2\n"
	
	modelObs = {}
	modelMeshes = {}
	boneIds = {}
	
	for object in bpy.data.objects:
		if object.type == 'ARMATURE':
			modelObs[object.name] = object
			
		if object.type == 'MESH':
			print ("Getting parent for mesh: %s" % object.name)
			parentArmOb = object.modifiers[0].object
			if not parentArmOb.name in modelMeshes:
				modelMeshes[parentArmOb.name] = []
			modelMeshes[parentArmOb.name].append(object)

	for modelObName in modelObs.keys():
	
		# Write Skeleton
		filedata += "skeleton\n"
		
		armOb = modelObs[modelObName]
		armature = armOb.data
		
		# Calc bone depths and sort
		boneDepths = []
		for bone in armature.bones.values():
			boneDepth = getBoneTreeDepth(bone, 0)
			boneDepths.append((bone, boneDepth))
		
		boneDepths = sorted(boneDepths, key=lambda k: k[0].name)
		boneDepths = sorted(boneDepths, key=lambda k: k[1])
		sortedBones = boneDepths
		
		for boneid, boneTuple in enumerate(sortedBones):
			boneIds[boneTuple[0].name] = boneid

		# Write World Bone
		filedata += '%d "%s" %d ' % (0, armOb.name, -1)   
		filedata += '%.8f %.8f %.8f ' % (0.0, 0.0, 0.0)
		filedata += '%.8f %.8f %.8f %.8f ' % (0.0, 0.0, 0.0, 1.0)
		filedata += '%.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f\n' % (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)
		
		for boneid, boneTuple in enumerate(sortedBones):
			bone = boneTuple[0]
			boneDepth = boneTuple[1]
			
			position, orientationQuat = getTranslationOrientation(bone, file)
			
			# Get Inverse World Matrix for bone
			x = bone.matrix_local.copy()
			x.transpose()
			t = Matrix([[-x[2][0], -x[2][1], -x[2][2], -x[2][3]],
						[x[1][0], x[1][1], x[1][2], x[1][3]],
						[x[0][0], x[0][1], x[0][2], x[0][3]],
						[x[3][0], x[3][1], x[3][2], x[3][3]]])
			t.invert()
			invWorldMatrix = Matrix([[t[0][1], -t[0][0], t[0][2], t[0][3]],
								[t[1][1], -t[1][0], t[1][2], t[1][3]],
								[t[2][1], -t[2][0], t[2][2], t[2][3]],
								[t[3][1], -t[3][0], t[3][2], t[3][3]]])
			
			outputBoneName = bone.name
			
			filedata += '%d "%s" ' % (boneid + 1, outputBoneName)   # Adjust bone ids + 1 as zero is the World Bone
			
			parentBoneId = 0
			if bone.parent:
				parentBoneId = boneIds[bone.parent.name] + 1   # Adjust bone ids + 1 as zero is the World Bone
			
			filedata += '%d ' % parentBoneId
			filedata +='%.8f %.8f %.8f ' % (position[0], position[1], position[2]) 
			filedata +='%.8f %.8f %.8f %.8f ' % (orientationQuat[1], orientationQuat[2], orientationQuat[3], orientationQuat[0]) # GR2 uses x,y,z,w for Quaternions rather than w,x,y,z
			filedata += '%.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f' % (invWorldMatrix[0][0], invWorldMatrix[0][1], invWorldMatrix[0][2], invWorldMatrix[0][3], 
																				invWorldMatrix[1][0], invWorldMatrix[1][1], invWorldMatrix[1][2], invWorldMatrix[1][3],
																				invWorldMatrix[2][0], invWorldMatrix[2][1], invWorldMatrix[2][2], invWorldMatrix[2][3],
																				invWorldMatrix[3][0], invWorldMatrix[3][1], invWorldMatrix[3][2], invWorldMatrix[3][3])
			#End of bone line
			filedata += "\n"
		
		filedata += 'meshes:%d\n' % len(modelMeshes[modelObName])
		
		for meshObject in modelMeshes[modelObName]:
			
			mesh = meshObject.data
			meshName = meshObject.name
			
			filedata += 'mesh:"%s"\n' % meshName
			
			parentArmOb = meshObject.modifiers[0].object
			
			weights = meshNormalizedWeights(meshObject, mesh)
			vertexBoneWeights = {}
			print (meshName)
			print ("len(weights[0])")
			print (len(weights[0]))
			for boneName in parentArmOb.data.bones.keys():
				vgroupDataForBone = getBoneWeights(boneName, weights)
				
				for vgData in vgroupDataForBone:
					vertexId = vgData[0]
					weight = vgData[1]
					if not vertexId in vertexBoneWeights:
						vertexBoneWeights[vertexId] = []
					vertexBoneWeights[vertexId].append((boneName, weight))
			
			print ("len(mesh.vertices)")
			print (len(mesh.vertices))
			print ("len(vertexBoneWeights.keys())")
			print (len(vertexBoneWeights.keys()))
			
			grannyVertexBoneWeights = {}
			for vertId in vertexBoneWeights.keys():
				
				rawBoneIdWeightTuples = []
				firstBoneId = 0
				for i in range(max(4,len(vertexBoneWeights[vertId]))):
					if i < len(vertexBoneWeights[vertId]):
						vertexBoneWeightTuple = vertexBoneWeights[vertId][i]
						boneName = vertexBoneWeightTuple[0]
						rawBoneIdWeightTuples.append((boneIds[boneName] + 1, vertexBoneWeightTuple[1]))
						if i == 0:
							firstBoneId = boneIds[boneName] + 1
					else:
						rawBoneIdWeightTuples.append((firstBoneId, 0))
				
				# Sort bone mappings by weight highest to lowest
				sortedBoneIdWeightTuples = sorted(rawBoneIdWeightTuples, key=lambda rawBoneIdWeightTuple: rawBoneIdWeightTuple[1], reverse=True)
				
				# Pick first four highest weighted bones
				boneIdsList = []
				rawBoneWeightsList = []
				for i in range(4): 
					boneIdsList.append(sortedBoneIdWeightTuples[i][0])
					rawBoneWeightsList.append(sortedBoneIdWeightTuples[i][1])
				
				rawWeightTotal = 0
				for weight in rawBoneWeightsList:
					rawWeightTotal = rawWeightTotal + weight
				
				boneWeightsList = []
				for weight in rawBoneWeightsList:
					calcWeight = round(255 * weight / rawWeightTotal)
					boneWeightsList.append(calcWeight)
					
				# Ensure that total of vertex bone weights is 255
				runningTotal = 0
				for i, weight in enumerate(boneWeightsList):
					runningTotal = runningTotal + weight
					if runningTotal > 255:
						boneWeightsList[i] = weight - 1
						break
				
				if runningTotal < 255:
					boneWeightsList[0] = boneWeightsList[0] + 1
				
				runningTotal = 0
				for i, weight in enumerate(boneWeightsList):
					runningTotal = runningTotal + weight
				
				if runningTotal != 255:
					raise "Error: Vertex bone weights do not total 255!"
				
				if not vertId in grannyVertexBoneWeights:
					grannyVertexBoneWeights[vertId] = []
				grannyVertexBoneWeights[vertId] = (boneIdsList, boneWeightsList)
			
			position, orientationQuat = getTranslationOrientation(meshObject, file)
			
			filedata += "vertices\n"

			# Determine unique vertex/UVs for output
			uniqueVertSet = set()
			uniqueVertUVIndexes = {}
			uniqueVertUVs = []
			currentVertUVIndex = 0
			
			currentTriangleId = 0
			triangleVertUVIndexes = []
			
			mesh.update(calc_tessface=True)
			#For each triangle
			for j, triangle in enumerate(mesh.tessfaces):
				vertIds = [v for v in triangle.vertices]
				vertIds = tuple(vertIds)
				triangleVertUVIndexes.append([])
				
				# For each vertex in triangle
				for i, uv in enumerate(mesh.tessface_uv_textures[0].data[j].uv):
					vertexId = vertIds[i]
					uvt = tuple(uv)
					vertSig = '%i|%.8f|%.8f' % (vertexId, uvt[0], uvt[1])
					
					if vertSig in uniqueVertSet:
						triangleVertUVIndex = uniqueVertUVIndexes[vertSig]
					else:
						uniqueVertSet.add(vertSig)
						uniqueVertUVIndexes[vertSig] = currentVertUVIndex
						uniqueVertUVs.append((vertexId, uvt[0], uvt[1]))
						triangleVertUVIndex = currentVertUVIndex
						currentVertUVIndex = currentVertUVIndex + 1
					
					triangleVertUVIndexes[currentTriangleId].append(triangleVertUVIndex)
				currentTriangleId = currentTriangleId + 1
			
			meshVerts = {}
			for i,vert in enumerate(mesh.vertices):
				meshVerts[i] = vert
			
			print ("uniqueVertUVs")
			print (len(uniqueVertUVs))
			print ("grannyVertexBoneWeights")
			print (len(grannyVertexBoneWeights))
			print ("Write Vertices")
			# Write Vertices
			for uniqueVertUV in uniqueVertUVs:
			
				index = uniqueVertUV[0]
				vert = meshVerts[index]
				vertCoord = tuple(vert.co)
				vertNormal = tuple(vert.normal)
				filedata +='%.8f %.8f %.8f ' % (vertCoord[0] + position[0],  vertCoord[1] +  position[1], 1 * (vertCoord[2] + position[2]))
				filedata +='%.8f %.8f %.8f ' % (vertNormal[0], vertNormal[1], vertNormal[2])
				filedata +='%.8f %.8f ' % (uniqueVertUV[1], 1 - uniqueVertUV[2])
				
				if index in grannyVertexBoneWeights:
					vBoneWeightTuple = grannyVertexBoneWeights[index]
				else:
					raise "Error: Mesh has unweighted vertices!"
					#vBoneWeightTuple = ([-1,-1,-1,-1],[-1,-1,-1,-1]) # Unweighted vertex - raise error
				
				filedata +='%d %d %d %d ' % (vBoneWeightTuple[0][0], vBoneWeightTuple[0][1],vBoneWeightTuple[0][2],vBoneWeightTuple[0][3]) # Bone Ids
				filedata +='%d %d %d %d\n' % (vBoneWeightTuple[1][0], vBoneWeightTuple[1][1],vBoneWeightTuple[1][2],vBoneWeightTuple[1][3]) # Bone Weights
			
			# Write Triangles
			filedata += "triangles\n"
			for triangle in triangleVertUVIndexes:
				filedata += '%i %i %i\n' % (triangle[0],triangle[1],triangle[2])
	
	filedata += "end"
	file.write(filedata)
	file.flush()
	file.close()
	print ("End BR2 Export.")
	return ""


###### IMPORT OPERATOR #######
class Import_br2(bpy.types.Operator, ExportHelper):

    bl_idname = "export_shape.br2"
    bl_label = "Export BR2 (.br2)"
    bl_description= "Export a Nexus Buddy .br2 file"
    filename_ext = ".br2"

    def execute(self, context):
        filepath = self.filepath
        filepath = bpy.path.ensure_ext(filepath, self.filename_ext)	
        do_export(context, filepath)
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager   
        wm.fileselect_add(self)
        return {'RUNNING_MODAL'}

### REGISTER ###

def menu_func(self, context):
    self.layout.operator(Import_br2.bl_idname, text="Nexus Buddy (.br2)")

 
def register():
    bpy.utils.register_module(__name__) 

    bpy.types.INFO_MT_file_export.append(menu_func)

def unregister():
    bpy.utils.unregister_module(__name__)

    bpy.types.INFO_MT_file_export.remove(menu_func)

if __name__ == "__main__":
    register()
