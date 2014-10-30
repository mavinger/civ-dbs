#!BPY

"""
Name: 'Civ 4 to Civ 5 Bone Renaming'
Blender: 249
Group: 'Object'
Tooltip: 'Civ 4 to Civ 5 Bone Renaming'
"""

import Blender

print "\n"
print "Civ 4 to Civ 5 Renaming"
print "\n"

scene = Blender.Scene.GetCurrent()

allObjects = scene.objects

boneMappingDictionary = {
	'BIP Pelvis': 'Base HumanPelvis', \
	'BIP Spine': 'Base HumanSpine1', \
	'BIP Spine1' : 'Base HumanSpine2', \
	'BIP Neck': 'Base HumanNeck1', \
	'BIP Head': 'Base HumanNeck2', \
	'BIP L Clavicle': 'Base HumanLCollarbone', \
	'BIP R Clavicle': 'Base HumanRCollarbone', \
	'BIP L UpperArm': 'Base HumanLUpperarm', \
	'BIP R UpperArm': 'Base HumanRUpperarm', \
	'BIP L Forearm': 'Base HumanLForearm', \
	'BIP R Forearm': 'Base HumanRForearm', \
	'BIP L Hand': 'Base HumanLPalm', \
	'BIP R Hand': 'Base HumanRPalm', \
	'BIP L Thigh': 'Base HumanLThigh', \
	'BIP R Thigh': 'Base HumanRThigh', \
	'BIP L Calf': 'Base HumanLCalf', \
	'BIP R Calf': 'Base HumanRCalf', \
	'BIP L Foot': 'Base HumanLFoot', \
	'BIP R Foot': 'Base HumanRFoot'
	} 
		
for object in allObjects:
	if object.type == 'Armature':
		armature = object.getData()
		armature.makeEditable()
		for bonename, bone in armature.bones.items():
			editBone = armature.bones[bonename] 
			for mappingkey in boneMappingDictionary:
				#print "Comparing %s with %s" % (bonename, mappingkey)
				if bonename == mappingkey:
					print "Updating %s to %s" % (bonename, boneMappingDictionary[mappingkey])
					editBone.name = boneMappingDictionary[mappingkey]
		armature.update()
		
	if object.type == 'Mesh':
		mesh = object.getData()
		for oldVertGroupName in mesh.getVertGroupNames():
			for mappingkey in boneMappingDictionary:
				if oldVertGroupName == mappingkey:
					newVertGroupName = boneMappingDictionary[mappingkey]
					mesh.addVertGroup(newVertGroupName)
					#mesh.assignVertsToGroup(oldVertGroupName, verts, 1.0, 1)
					mesh.removeVertGroup(oldVertGroupName)

