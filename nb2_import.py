#!BPY
""" 
Name: 'Nexus Buddy 2 (.nb2)...'
Blender: 245
Group: 'Import'
Tooltip: 'Import from Nexus Buddy 2 file format (.nb2)'
"""
# Original Milkshape ASCII Txt Import:
# Author: Markus Ilmola
# Email: markus.ilmola@pp.inet.fi
#
# Additional changes by Deliverator
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#

# import needed stuff
import os.path
import re
import math
from math import *
import Blender
from Blender import Mathutils, Window, Draw
from Blender.Mathutils import *

GLOBALS = {}
EVENT_NONE = 0
EVENT_EXIT = 1
EVENT_REDRAW = 2
EVENT_FILESEL = 3

# Converts ms3d euler angles to a rotation matrix
def RM(a):
	sy = sin(a[2])
	cy = cos(a[2])
	sp = sin(a[1])
	cp = cos(a[1])
	sr = sin(a[0])
	cr = cos(a[0])
	return Matrix([cp*cy, cp*sy, -sp], [sr*sp*cy+cr*-sy, sr*sp*sy+cr*cy, sr*cp],[cr*sp*cy+-sr*-sy, cr*sp*sy+-sr*cy, cr*cp])

# Converts ms3d euler angles to a quaternion
def RQ(a):
	angle = a[2] * 0.5;
	sy = sin(angle);
	cy = cos(angle);
	angle = a[1] * 0.5;
	sp = sin(angle);
	cp = cos(angle);
	angle = a[0] * 0.5;
	sr = sin(angle);
	cr = cos(angle);
	return Quaternion(cr*cp*cy+sr*sp*sy, sr*cp*cy-cr*sp*sy, cr*sp*cy+sr*cp*sy, cr*cp*sy-sr*sp*cy)

# takes a texture filename and tries to load it
def loadImage(path, filename):
	image = None
	try:
		image = Blender.Image.Load(os.path.abspath(filename))
	except IOError:
		print "Warning: Failed to or: " + filename + ". Trying short path instead...\n"
		try:
			image = Blender.Image.Load(os.path.dirname(path) + "/" + os.path.basename(filename))
		except IOError:
			print "Warning: Failed to load image: " + os.path.basename(filename) + "!\n"
	return image

# returns the next non-empty, non-comment line from the file
def getNextLine(file):
	ready = False
	while ready==False:
		line = file.readline()
		if len(line)==0:
			print "Warning: End of file reached."
			return line
		ready = True
		line = line.strip()
		if len(line)==0 or line.isspace():
			ready = False
		if len(line)>=2 and line[0]=='/' and line[1]=='/':
			ready = False
	return line	
	
# imports a MilkShape3D ascii file to the current scene
def import_ms3d_ascii(path):
	# limits
	MAX_NUMMESHES = 1000
	MAX_NUMVERTS = 100000
	MAX_NUMNORMALS = 100000
	MAX_NUMTRIS = 100000
	MAX_NUMMATS = 16
	MAX_NUMBONES = 1000
	MAX_NUMPOSKEYS = 1000
	MAX_NUMROTKEYS = 1000

	# get scene
	scn = Blender.Scene.GetCurrent()
	if scn==None:
		return "No scene to import to!"

	# open the file
	try:
		file = open(path, 'r')
	except IOError:
		return "Failed to open the file!"
	
	try:
		if not path.endswith(".nb2"):
			raise IOError
	except IOError:
		return "Must be an nb2 file!"
		
	# Read frame info
	try:
		lines = getNextLine(file).split()
		if len(lines) != 2 or lines[0] != "Frames:":
			raise ValueError
		lines = getNextLine(file).split()
		if len(lines) != 2 or lines[0] != "Frame:":
			raise ValueError
	except ValueError:
		return "Frame information is invalid!"

	# Create the mesh
	meshName = "Mesh Object"
	meshOb = Blender.Object.New('Mesh', meshName)
	mesh = Blender.Mesh.New(meshName)
	meshOb.link(mesh)
	scn.objects.link(meshOb)

	# read the number of meshes
	try:
		lines = getNextLine(file).split()
		if len(lines)!=2 or lines[0]!="Meshes:":
			raise ValueError
		numMeshes = int(lines[1])
		if numMeshes < 0 or numMeshes > MAX_NUMMESHES:
			raise ValueError
	except ValueError:
		return "Number of meshes is invalid!"

	# read meshes
	vertBase = 0
	faceBase = 0
	boneIds = [[],[],[],[]]
	boneWeights = [[],[],[],[]]
	meshVertexGroups = {}
	vCount = 0
	for i in range(numMeshes):
		# read name, flags and material
		try:
			lines = re.findall(r'\".*\"|[^ ]+', getNextLine(file))
			if len(lines)!=3:
				raise ValueError
			meshName = lines[0]
			meshName = meshName[1:-1]
			print 'processing mesh name:%s...' % meshName
			material = int(lines[2])
		except ValueError:
			return "Name, flags or material in mesh " + str(i+1) + " are invalid!"
		
		# read the number of vertices
		try:
			numVerts = int(getNextLine(file))
			if numVerts < 0 or numVerts > MAX_NUMVERTS:
				raise ValueError
		except ValueError:
			return "Number of vertices in mesh " + str(i+1) + " is invalid!"
			
		print 'Number of vertices in mesh:%d' % numVerts
		
		# read vertices
		coords = []
		uvs = []
		for j in xrange(numVerts):
			try:
				lines = getNextLine(file).split()
				#print '%d:len(lines):%d' % (j,len(lines))
				if len(lines)!=14:
					raise ValueError
				coords.append([float(lines[1]), float(lines[2]), float(lines[3])])
				uvs.append([float(lines[4]), 1-float(lines[5])])
				boneIds[0].append(int(lines[6]))
				boneWeights[0].append(float(lines[7]))
				boneIds[1].append(int(lines[8]))
				boneWeights[1].append(float(lines[9]))
				boneIds[2].append(int(lines[10]))
				boneWeights[2].append(float(lines[11]))
				boneIds[3].append(int(lines[12]))
				boneWeights[3].append(float(lines[13]))
				meshVertexGroups[vCount] = meshName     # uses the long mesh name - may be > 21 chars
				vCount += 1
			except ValueError:
				return "Vertex " + str(j+1) + " in mesh " + str(i+1) + " is invalid!"
		mesh.verts.extend(coords)
		

		
		# read number of normals
		try:
			numNormals = int(getNextLine(file))
			if numNormals < 0 or numNormals > MAX_NUMNORMALS:
				raise ValueError
		except ValueError:
			return "Number of normals in mesh " + str(i+1) + " is invalid!"

		print 'Number of normals in mesh:%d' % numNormals
			
		# read normals
		normals = []
		for j in xrange(numNormals):
			try:
				lines = getNextLine(file).split()
				if len(lines)!=3:
					raise ValueError
				normals.append([float(lines[0]), float(lines[1]), float(lines[2])])
			except ValueError:
				return "Normal " + str(j+1) + " in mesh " + str(i+1) + " is invalid!"

		# read the number of triangles
		try:
			numTris = int(getNextLine(file))
			if numTris < 0 or numTris > MAX_NUMTRIS:
				raise ValueError
		except ValueError:
			return "Number of triangles in mesh " + str(i+1) + " is invalid!"

		print 'Number of triangles in mesh:%d' % numTris
			
		# read triangles
		faces = []
		for j in xrange(numTris):
			# read the triangle
			try:
				lines = getNextLine(file).split()
				if len(lines)!=8:
					raise ValueError
				v1 = int(lines[1])
				v2 = int(lines[2])
				v3 = int(lines[3])
				faces.append([v1+vertBase, v2+vertBase, v3+vertBase])
			except ValueError:
				return "Triangle " + str(j+1) + " in mesh " + str(i+1) + " is invalid!"
		
		mesh.faces.extend(faces)
		# set texture coordinates and material
		for j in xrange(faceBase, len(mesh.faces)):
			face = mesh.faces[j]
			face.uv = [Vector(uvs[face.verts[0].index-vertBase]), Vector(uvs[face.verts[1].index-vertBase]), Vector(uvs[face.verts[2].index-vertBase])]
			if material>=0:
				face.mat = material

		# increase vertex and face base
		vertBase = len(mesh.verts)
		faceBase = len(mesh.faces)

	# read the number of materials
	try:
		lines = getNextLine(file).split()
		if len(lines)!=2 or lines[0]!="Materials:":
			raise ValueError
		numMats = int(lines[1])
		if numMats < 0 or numMats > MAX_NUMMATS:
			raise ValueError
	except ValueError:
		return "Number of materials is invalid!"

	# read the materials
	for i in range(numMats):
			# read name
			name = getNextLine(file)[1:-1]

			# create the material
			mat = Blender.Material.New(name)
			mesh.materials += [mat]

			# read ambient color
			try:
				lines = getNextLine(file).split()
				if len(lines)!=4:
					raise ValueError
				amb = (float(lines[0])+float(lines[1])+float(lines[2]))/3
				mat.setAmb(amb)
			except ValueError:
				return "Ambient color in material " + str(i+1) + " is invalid!"

			# read diffuse color
			try:
				lines = getNextLine(file).split()
				if len(lines)!=4:
					raise ValueError
				mat.setRGBCol([float(lines[0]), float(lines[1]), float(lines[2])])
			except ValueError:
				return "Diffuse color in material " + str(i+1) + " is invalid!"

			# read specular color
			try:
				lines = getNextLine(file).split()
				if len(lines)!=4:
					raise ValueError
				mat.setSpecCol([float(lines[0]), float(lines[1]), float(lines[2])])
			except ValueError:
				return "Specular color in material " + str(i+1) + " is invalid!"

			# read emissive color
			try:
				lines = getNextLine(file).split()
				if len(lines)!=4:
					raise ValueError
				emit = (float(lines[0])+float(lines[1])+float(lines[2]))/3
				mat.setEmit(emit)
			except ValueError:
				return "Emissive color in material " + str(i+1) + " is invalid!"

			# read shininess
			try:
				shi = float(getNextLine(file))
				#mat.setHardness(int(shi))
			except ValueError:
				return "Shininess in material " + str(i+1) + " is invalid!"

			# read transparency
			try:
				alpha = float(getNextLine(file))
				mat.setAlpha(alpha)
				if alpha < 1:
					 mat.mode |= Blender.Material.Modes.ZTRANSP
			except ValueError:
				return "Transparency in material " + str(i+1) + " is invalid!"

			# read texturemap
			texturemap = getNextLine(file)[1:-1]
			if len(texturemap)>0:
				colorTexture = Blender.Texture.New(name + "_texture")
				colorTexture.setType('Image')
				#colorTexture.setImage(loadImage(path, texturemap))
				mat.setTexture(0, colorTexture, Blender.Texture.TexCo.UV, Blender.Texture.MapTo.COL)

			# read alphamap
			alphamap = getNextLine(file)[1:-1]
			if len(alphamap)>0:
				alphaTexture = Blender.Texture.New(name + "_alpha")
				alphaTexture.setType('Image') 
				#alphaTexture.setImage(loadImage(path, alphamap))
				mat.setTexture(1, alphaTexture, Blender.Texture.TexCo.UV, Blender.Texture.MapTo.ALPHA)		

	# read the number of bones
	try:
		lines = getNextLine(file).split()
		if len(lines)!=2 or lines[0]!="Bones:":
			raise ValueError
		numBones = int(lines[1])
		if numBones < 0 or numBones > MAX_NUMBONES:
			raise ValueError
	except:
		return "Number of bones is invalid!"

	# create the armature
	armature = None
	armOb = None
	
	print "numBones:"
	
	numBones
	if numBones > 0:
		armOb = Blender.Object.New('Armature', "ArmatureObject")
		armature = Blender.Armature.New("Armature")
		armature.drawType = Blender.Armature.STICK
		armOb.link(armature)
		scn.objects.link(armOb)
		armOb.makeParentDeform([meshOb])
		armature.makeEditable()

	# read bones
	posKeys = {}
	rotKeys = {}
	boneNames = []
	boneNameDict = {}
	for i in range(numBones):
		# read name
		fullName = getNextLine(file)[1:-1]
		
		boneNameCount = {}
		# store bone full names in armature object
		if (len(fullName) > 31):
			boneName29 = "%s|%s" % (fullName[:14], fullName[-13:])
			if not boneName29 in boneNameCount:
				boneNameCount[boneName29] = 0
				
			name = "%s%02d%s" % (fullName[:14], boneNameCount[boneName29], fullName[-13:])
			armOb.addProperty("B_" + name, fullName);
			boneNameCount[boneName29] = boneNameCount[boneName29] + 1
			print 'Bone Rename: "%s" > "%s" ' % (fullName, name);
		else:
			name = fullName
		
		# create the bone
		bone = Blender.Armature.Editbone()
		armature.bones[name] = bone
		boneNames.append(name)
		boneNameDict[fullName] = name
		
		# read parent
		fileParentBoneName = getNextLine(file)[1:-1]
		if len(fileParentBoneName) > 0:
			parentBoneName = boneNameDict[fileParentBoneName]
			bone.parent = armature.bones[parentBoneName]

		# read position and rotation
		try:
			line = getNextLine(file)
			lines = line.split()
			if len(lines) != 8:
				raise ValueError
			pos = [float(lines[1]), float(lines[2]), float(lines[3])]
			quat = [float(lines[4]), float(lines[5]), float(lines[6]), float(lines[7])]
			#print 'Read bone: %s' % line
		except ValueError:
			return "Invalid position or orientation in a bone!"

		# Granny Rotation Quaternions are stored X,Y,Z,W but Blender uses W,X,Y,Z
		quaternion = Quaternion(quat[3], quat[0], quat[1], quat[2]) 
		rotMatrix = quaternion.toMatrix()
		
		boneLength = 1
		# set position and orientation
		if bone.hasParent():
			bone.head =  Vector(pos) * bone.parent.matrix + bone.parent.head
			bone.tail = bone.head + Vector([boneLength,0,0])
			tempM = rotMatrix * bone.parent.matrix 
			#tempM.transpose;
			bone.matrix = tempM
		else:
			bone.head = Vector(pos)
			bone.tail = bone.head + Vector([boneLength,0,0])
			bone.matrix = rotMatrix 

		# read the number of position key frames
		try:
			numPosKeys = int(getNextLine(file))
			if numPosKeys < 0 or numPosKeys > MAX_NUMPOSKEYS:
				raise ValueError
		except ValueError:
			return "Invalid number of position key frames!"

		# read position key frames
		posKeys[name] = []
		for j in range(numPosKeys):
			# read time and position
			try:
				lines = getNextLine(file).split()
				if len(lines) != 4:
					raise ValueError
				time = float(lines[0])
				pos = [float(lines[1]), float(lines[2]), float(lines[3])]
				posKeys[name].append([time, pos])
			except ValueError:
				return "Invalid position key frame!"
			
		# read the number of rotation key frames
		try:
			numRotKeys = int(getNextLine(file))
			if numRotKeys < 0 or numRotKeys > MAX_NUMROTKEYS:
				raise ValueError
		except ValueError:
			return "Invalid number of rotation key frames!"

		# read rotation key frames
		rotKeys[name] = []
		for j in range(numRotKeys):
			# read time and rotation
			try:
				lines = getNextLine(file).split()
				if len(lines) != 4:
					raise ValueError
				time = float(lines[0])
				rot = [float(lines[1]), float(lines[2]), float(lines[3])]
				rotKeys[name].append([time, rot])
			except ValueError:
				return "Invalid rotation key frame!"
	
	# Handle mesh names > 21 characters and ensure sure names are unique
	meshList = []
	meshNameDict = {}
	meshNameCount = {}
	for meshName in set(meshVertexGroups.itervalues()):
		meshName19 = "%s|%s" % (meshName[:9], meshName[-8:])
		meshNameCount[meshName19] = 0
		
	for meshName in set(meshVertexGroups.itervalues()):
		meshName19 = "%s|%s" % (meshName[:9], meshName[-8:])
		if (len(meshName) > 21):
			shortMeshName = "%s%02d%s" % (meshName[:9], meshNameCount[meshName19], meshName[-8:])
			print "Mesh Rename: (%s) %s > %s" % (meshName19, meshName, shortMeshName)
			armOb.addProperty("M_" + shortMeshName, meshName);
		else:
			shortMeshName = meshName
			
		meshList.append(shortMeshName)
		meshNameDict[meshName] = shortMeshName
		meshNameCount[meshName19] = meshNameCount[meshName19] + 1
		
	newMeshes = {}
	print '%d Meshes Detected' % len(meshList)
	
	for longMeshName, vgName in meshNameDict.iteritems():
		newMeshName = vgName
		newMeshOb = Blender.Object.New('Mesh', newMeshName)
		newMesh = mesh.__copy__()
		newMeshOb.link(newMesh)
		scn.objects.link(newMeshOb)
		
		for dummy, vgName2 in meshNameDict.iteritems():
			newMesh.addVertGroup(vgName2)
			
		for key in meshVertexGroups:
			#print '>>> %d %s' % (key, meshVertexGroups[key])
			vgLongName = meshVertexGroups[key]
			vgShortName = meshNameDict[vgLongName]
			newMesh.assignVertsToGroup(vgShortName, [key], 1.0, 1)
			
		for i in range(numBones):
			# Create vertex group for this bone
			name = boneNames[i] # bone/vertex group names cannot be longer than 31 chars!
			newMesh.addVertGroup(name)
			
			for j in range(4):
				for index, v in enumerate(boneIds[j]):
					if v==i:
						#print 'as: %s %d, %f' % (name, index, boneWeights[j][index])
						newMesh.assignVertsToGroup(name, [index], boneWeights[j][index], Blender.Mesh.AssignModes.ADD)
						#vgroup.append(index)
						
				#if (len(vgroup) > 0):
					#print 'Assigning Vert Group %s' % name
					
				
			#else:
				#print 'Removing Vert Group %s' % name
			#	newMesh.removeVertGroup(name)
		
		armOb.makeParentDeform([newMeshOb])
		
		newMeshes[newMeshName] = newMesh
		
	for key in newMeshes:
		nmesh = newMeshes[key]
		
		for xMeshName in meshList:
			if xMeshName != key:
				#print 'Get Mesh Verts: %s %s' % (key, xMeshName)
				verts = nmesh.getVertsFromGroup(xMeshName)
				nmesh.verts.delete(verts)
				
			nmesh.removeVertGroup(xMeshName)
			
		for vertGroup in nmesh.getVertGroupNames():
			#print 'Test %s > %s' % (key, vertGroup)
			vertCountForGroup = nmesh.getVertsFromGroup(vertGroup)     
			if len(vertCountForGroup) == 0:
				nmesh.removeVertGroup(vertGroup)
		
		if GLOBALS['DO_MESH_ROTATION_90'].val:
			# Rotate meshes 90 degrees about X axis
			transMatrix90x =  Matrix([1,0,0,0],[0,0,-1,0],[0,1,0,0],[0,0,0,1])
			nmesh.transform(transMatrix90x)
		
		# Remove vertex doubles
		#nmesh.remDoubles(0)
	
	scn.objects.unlink(meshOb)
	armature.update()
	
	# Rotation Fix for Bones
	armature.makeEditable()
	for i in range(numBones):
		bone = armature.bones[boneNames[i]]
		
		if bone.hasParent():
			transMatrix =  Matrix(	[-bone.matrix[1][0], -bone.matrix[1][1], -bone.matrix[1][2]],
									[bone.matrix[0][0], bone.matrix[0][1], bone.matrix[0][2]], 
									[bone.matrix[2][0], bone.matrix[2][1], bone.matrix[2][2]])
			
			bone.matrix = transMatrix
			
			roll = bone.roll
			bone.roll = roll + 90
		
	# create action and pose
	action = None
	pose = None
	if armature != None:
		armature.update()
		pose = armOb.getPose()
		action = armOb.getAction()
		if not action:
			action = Blender.Armature.NLA.NewAction()
			action.setActive(armOb)

	# create animation key frames
	for name, pbone in pose.bones.items():
		# create position keys
		for key in posKeys[name]:
			pbone.loc = Vector(key[1])
			pbone.insertKey(armOb, int(key[0]+0.5), Blender.Object.Pose.LOC, True)

		# create rotation keys
		for key in rotKeys[name]:
			pbone.quat = RQ(key[1])
			pbone.insertKey(armOb, int(key[0]+0.5), Blender.Object.Pose.ROT, True)	

	if GLOBALS['DELETE_TOP_BONE'].val:
		# Adjust object names, remove top bone for Civ V - Deliverator
		armature.makeEditable()
		
		bone = armature.bones[boneNames[0]]
		while not bone.parent is None:
			bone = bone.parent
		
		print 'Found World Bone: %s' % bone.name
		
		name = bone.name
		armOb.name = name
		
		# Delete top bone unless that would leave zero bones
		if (len(armature.bones) > 1):
			del armature.bones[name]
			
		armature.update()
	
	# set the imported object to be the selected one
	scn.objects.selected = []
	Blender.Redraw()

	# The import was a succes!
	return ""

# load the model
def fileCallback(filename):
	error = import_ms3d_ascii(filename)
	if error!="":
		Blender.Draw.PupMenu("An error occured during import: " + error + "|Not all data might have been imported succesfully.", 2)

def nb2_ui_exit(e,v):
	GLOBALS['EVENT'] = e

def do_redraw(e,v):		GLOBALS['EVENT'] = e

def nb2_ui():
	# Only to center the UI
	x,y = GLOBALS['MOUSE']
	x -= 180; y -= 0 # offset... just to get it centered
	
	Draw.Label('Import NB2 - Options', x+25,y+165, 200, 20)
	
	GLOBALS['DO_MESH_ROTATION_90'] = Draw.Toggle('Rotate Meshes 90 degrees', EVENT_REDRAW, x+25,  y+135, 200, 20, GLOBALS['DO_MESH_ROTATION_90'].val, 'Rotate Meshes 90 degrees', do_redraw)
	GLOBALS['DELETE_TOP_BONE'] = Draw.Toggle('Delete Top Bone', EVENT_REDRAW, x+25,  y+105, 200, 20, GLOBALS['DELETE_TOP_BONE'].val, 'Delete Top Bone', do_redraw)
	
	Draw.PushButton('Cancel', EVENT_EXIT, x+130, y-160, 100, 20, 'Exit the importer', nb2_ui_exit)
	Draw.PushButton('Import NB2', EVENT_FILESEL, x+240, y-160, 100, 20, 'Import the NB2 File', do_redraw)
	
def write_ui():
	# globals
	GLOBALS['EVENT'] = EVENT_REDRAW
	GLOBALS['MOUSE'] = [i/2 for i in Window.GetScreenSize()]
	GLOBALS['DO_MESH_ROTATION_90'] = Draw.Create(1)
	GLOBALS['DELETE_TOP_BONE'] = Draw.Create(1)
	
	# hack so the toggle buttons redraw. this is not nice at all
	while GLOBALS['EVENT'] != EVENT_EXIT:
		
		if GLOBALS['EVENT'] == EVENT_FILESEL:
			Blender.Window.FileSelector(fileCallback, 'Import')
			break
		
		Draw.UIBlock(nb2_ui, 0)
	
if __name__ == '__main__':
	if not set:
		Draw.PupMenu('Error%t|A full install of python2.3 or python 2.4+ is needed to run this script.')
	else:
		write_ui()
