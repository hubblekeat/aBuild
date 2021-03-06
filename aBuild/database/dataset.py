
from aBuild import msg
from aBuild.utility import chdir, _get_reporoot

class dataset:

    def __init__(self,dset,systemSpecies):
        from os import path,makedirs
        from aBuild.database.crystal import Crystal
        from aBuild.calculators.vasp import VASP

        self.crystals = dset
        self.species = dset[0].crystalSpecies

        
#        self.calculator = calculator


#        if isinstance(dset,list):
#            
##            if isinstance(dset[0], dict):
##                self.init_enum(dset,systemSpecies)
#            elif isinstance(dset[0], Crystal):
#                self.crystals = dset
#                self.nCrystals = len(dset)
#            elif isinstance(dset[0], VASP):
#                self.calcs = dset
#                self.nCalcs = len(dset)
##            elif isinstance(dset[0],str):
##                self.init_paths(dset,systemSpecies)
##        elif isinstance(dset, str):
##           self.init_file(dset,lFormat)

#        self.root = root

        
    # Used to be called 'buildFoldersFromEnum
    @staticmethod
    def init_enum(enumdicts,systemSpecies):
        from aBuild.enumeration import Enumerate
        from aBuild.calculators.vasp import VASP
        from aBuild.database.crystal import Crystal
        from aBuild.jobs import Job
        from random import randrange
        from aBuild.utility import chdir
        from numpy import array
        from os import remove, path

        #        from crystal import Crystal
        from os import path
        import os

        print("Building database from enumerations")
        crystals = []
        #        configIndex = startPoint = self._starting_point
        for eDict in enumdicts:
            enumController = Enumerate(eDict)
            if enumController.nEnumStructs == 0:
                msg.warn('There are no enumerated structures for lattice type {}.  Not building any VASP folders for them.'.format(eDict["lattice"]))
                enumController.buildInputFile()

                enumController.enumerate()

            # Loop to generate random structures for a given lattice type
            for i in range(eDict["nconfigs"]):
#                rStruct = 16254#randrange(1,enumController.nEnumStructs)
                print('Adding {} structure # {} to database'.format(eDict["lattice"],rStruct) )
                with open('structNums','a+') as f:
                    f.write(eDict["name"] + ' ' + str(rStruct) + '\n')
                    #print("Building VASP folder for {} structure #: {}".format(eDict["lattice"],rStruct))
                enumController.generatePOSCAR(rStruct)

                
                poscarpath = path.join(enumController.root,"poscar.{}.{}".format(eDict["name"],rStruct))
                thisCrystal = Crystal.from_poscar(poscarpath, systemSpecies) #title = ' '.join([self.enumDicts[index]["lattice"]," str #: {}"]).format(rStruct)
                crystals.append(thisCrystal)
                delpath = path.join(enumController.root,"poscar.{}.{}".format(eDict["name"],rStruct))
                remove(delpath)
        return dataset(crystals)

    # Sometimes an entire dataset is stored in one file.  I'd like to extract each crystal from the file to 
    # create a list of crystal objects
    @staticmethod
    def from_file(datafile,species,linesformat):
        from os import path
        handler = {'new_training.cfg':lambda file: dataset._init_mlp(file),'train.cfg': 'mlptrain','structures.in':'ce',}
        if 'relaxed' in datafile:
            handler[path.split(datafile)[-1]] = lambda file: dataset._init_mlp(file,species)
        if 'dataReport' in datafile:
            handler[path.split(datafile)[-1]] = lambda file: dataset._init_dataReport(file,species)
        if 'train' in datafile:
            handler[path.split(datafile)[-1]] = lambda file: dataset._init_mlp(file,species)
        #selectedFile = path.join(self.root,'new_training.cfg')
        print(handler, 'handler')
        return handler[path.split(datafile)[-1]](datafile)

    def _init_dataReport(self,datafile):
        with open(datafile,'r') as f:
            lines = f.readlines()

        del lines[:4]
        self.formationenergies = [ float(x.split()[-5]) for x in lines]
        self.concs = [ float(x.split()[-4]) for x in lines]
        self.titles = [' '.join(x.split()[:-7]) for x in lines]

    @staticmethod
    def _init_mlp(datafile,species):
        from aBuild.database.crystal import Crystal
        import os
        from os import path
        from aBuild.calculators.vasp import VASP
        from aBuild.calculators.aflow import AFLOW
        with open(datafile,'r') as f:
            lines = f.readlines()

        crystals = []
        nCrystals = 0
        # Get information for pures so I can calculate formation energies 
        root = os.getcwd()


        for index,line in enumerate(lines):
            if 'BEGIN' in line:
                indexStart = index
            elif 'END' in line:
                indexEnd = index
                structlines = lines[indexStart:indexEnd + 1]
                print("Processed {} crystals".format(nCrystals))
                nCrystals += 1
                
                thisCrystal = Crystal.from_lines(structlines,species,'mlp')
                if thisCrystal.minDist > 1.5:
                    if thisCrystal.results["energyF"] != None:
                        try:
                            # Try to get the formation enthalpy if possible.
                            pures = [VASP.from_path(path.join(root,'training_set','pure' + x))   for x in species]
                            puresDict = {}
                            for ispec,spec in enumerate(species):
                                pures[ispec].read_results()
                            thisCrystal.results["fEnth"] = thisCrystal.results["energyF"]/thisCrystal.nAtoms - sum(   [ pures[i].crystal.results["energyF"]/pures[i].crystal.nAtoms * thisCrystal.concentrations[i] for i in range(thisCrystal.nTypes)])
                        except:
                            # If pure information is not available, not possible to get formation ener
                            thisCrystal.results["fEnth"] = None
                    crystals.append(thisCrystal)
                else:
                    msg.warn("Mindist is pretty small for this one, so I'm not gonna add it")
#                if thisCrystal.results == None:
#                    if thisCrystal.minDist > 1.5:
#                        self.crystals.append(thisCrystal)
#                else:
#                    if thisCrystal.results["energyF"] < 100 and thisCrystal.minDist > 1.5:
#                        self.crystals.append(thisCrystal)
#                    else:
#                        print("Not adding structure {}.  Seems like an extreme one.".format(thisCrystal.title))
#                        print("Energy: {}".format(thisCrystal.results["energyF"]))
#                        print("MinDist: {}".format(thisCrystal.minDist))

        return dataset(crystals,species)

    @staticmethod
    def from_paths(paths,systemSpecies,calculator='VASP'):
        from aBuild.database.crystal import Crystal
        from aBuild.calculators.vasp import VASP
        from aBuild.calculators.aflow import AFLOW
        
        from aBuild.calculators.lammps import LAMMPS
        from os import path
        
        crystals = []
        for dirpath in paths:
            if calculator == 'VASP':
                if path.isfile(path.join(dirpath,'aflow.in')):
                    print("Initializing AFLOW object from path: {}".format(dirpath))
                    calc = AFLOW.from_path(dirpath,systemSpecies)
                    calc.read_results()
                else:
                    calc = VASP.from_path(dirpath)
                    calc.read_results()

            #Added for LAMMPS compatibility
            if calculator == 'LAMMPS':
                calc = LAMMPS(dirpath,systemSpecies)
                calc.read_results()

                
            if calc.crystal.results is not None:
                print("Adding Crystal")
                crystals.append(calc.crystal)
        species = crystals[0].systemSpecies
        return dataset(crystals,species)
            

    def starting_point(self,folderpath):
        from os import path
        from glob import glob
        from aBuild.utility import chdir

        with chdir(folderpath):
            dirsE = glob('E.*')
            dirsA = glob('A.*')
        prevCalcs = [int(x.split('.')[1])  for x in dirsE] + [int(x.split('.')[1])  for x in dirsA]
        prevCalcs.sort()
        if prevCalcs != []:
            return prevCalcs[-1] + 1
        else:
            return 1

        #    def write(self):

        
    def buildFolders(self,buildpath,calculator,runGetKpoints = True,foldername = 'A'):
        from os import path
        from aBuild.calculators.vasp import VASP
        from aBuild.calculators.aflow import AFLOW
        from aBuild.calculators.lammps import LAMMPS
        from aBuild.calculators.espresso import ESPRESSO
        from aBuild.jobs import Job
        from math import floor
        import os

        print("Building folders in {}".format(buildpath))
        if not path.isdir(buildpath):
                os.mkdir(buildpath)
                print('Made path:',buildpath)
        configIndex = startPoint = self.starting_point(buildpath)

        lookupCalc = {'aflow': lambda specs: AFLOW.from_dictionary(specs),
                      'vasp': lambda specs: VASP.from_dictionary(specs,self.species),
                      'qe': lambda specs: ESPRESSO(specs,self.species),
                      'lammps': lambda specs: LAMMPS(specs,self.species)}

#        lookupSpecs = {'vasp': lambda crystal: {"incar":calculator["vasp"]["incar"],"kpoints":calculator["vasp"]["kpoints"], 'potcar':calculator["vasp"]["potcars"],"crystal":crystal},
 #                 'qe': lambda crystal : {"crystal":crystal, "pseudopotentials":calculator["qe"]["pseudopotentials"]},
  #                    'lammps': lambda crystal: {"crystal":crystal, "potential":calculator["lammps"]["potential"]} }

        lookupBuild = {'aflow': lambda obj: obj.buildFolder(),
                       'vasp': lambda obj: obj.buildFolder(runGetKPoints = runGetKpoints),
                       'qe': lambda obj:obj.buildFolder(),
                      'lammps': lambda obj: obj.buildFolder()} 

        for crystal in self.crystals:
            print("Building crystal {}".format(crystal.title))
            runpath = path.join(buildpath,foldername + ".{}".format(configIndex) )
            #Augment the existing dictionary in preparation for sending it in
            calculator[calculator["active"]]["crystal"] = crystal
            calculator[calculator["active"]]["species"] = self.species
            calculator[calculator["active"]]["directory"] = runpath
            
            # Initialize the calculation object
            print('initializing VASP object')
            thisCalc = lookupCalc[calculator["active"]](calculator[calculator["active"]])

#            if 'AFM' in calculator[calculator["active"]] and thisCalc.crystal.AFMPlanes == None:
#                msg.info("Skipping this structure because I can't find the AFM planes")
#                continue
            
            # Build the path
            if not path.isdir(runpath):
                os.mkdir(runpath)
            else:
                msg.fatal("I'm gonna write over top of a current directory. ({})  I think I'll stop instead.".format(runpath))

                # Change the directory and build the folder
            print("Building folder for structure: {}".format(crystal.title) )
            with chdir(runpath):
                success = lookupBuild[calculator["active"]](thisCalc)
            if not success:
                if calculator["active"] == 'aflow':
                    retryCalc = lookupCalc["vasp"](calculator['vasp'])
                    with chdir(runpath):
                        success = lookupBuild["vasp"](retryCalc)
                    if not success:
                        msg.fatal("I tried building an aflow dir and it failed, then I tried building a VASP dir and it failed too. I give up")
                else:
                    msg.warn("VASP(??) directory build failed, and I'm not sure why")
                    
            configIndex += 1
            

        # Build the submission script
        exdir = path.join(buildpath,'A.')
        if calculator['active'] == 'aflow':
            calculator["execution"]["exec_path"] = "aflow --run"
        elif calculator["active"] == 'vasp':
            calculator["execution"]["exec_path"] = "vasp6_serial"

        
        startAdder = int(floor(startPoint/1000)) * 1000
        endAdder = int(floor((configIndex - 1)/1000)) * 1000

        if startAdder == endAdder:  # Don't need to submit two jobs in this case.  Just one, but we might have to add an offset if the numbers are too high.
            msg.info("Building one job submission file")
            calculator["execution"]["offset"] = startAdder 
            mljob = Job(calculator["execution"],exdir,calculator["execution"]["exec_path"], arrayStart = startPoint-startAdder,arrayEnd = configIndex - 1 - endAdder)
            with chdir(buildpath):
                print('Building job file')
                mljob.write_jobfile('jobscript_vasp.sh')
        else:  # We're going to have to submit two jobs to span the whole job array.
            msg.info("Building two job submission files")
            #First job..
            calculator["execution"]["offset"] = startAdder 
            mljob = Job(calculator["execution"],exdir,calculator["execution"]["exec_path"], arrayStart = startPoint - startAdder,arrayEnd = 999)
            with chdir(buildpath):
                print('Building job file')
                mljob.write_jobfile('jobscript_vasp_1.sh')
                    
            calculator["execution"]["offset"] = endAdder - 1
            mljob = Job(calculator["execution"],exdir,calculator["execution"]["exec_path"], arrayStart = 1,arrayEnd = configIndex - endAdder)
            with chdir(buildpath):
                print('Building job file')
                mljob.write_jobfile('jobscript_vasp_2.sh')
                





        
    


    def build_relax_select_input(self):
        from os import remove,path
        from aBuild.enumeration import Enumerate
        from aBuild.database.crystal import Crystal
        from aBuild.fitting.mtp import MTP
        from aBuild.utility import unpackProtos,getAllPerms
        from glob import glob
        fittingRoot = path.join(self.root,'fitting','mtp')
        
        for ilat  in range(self.nEnums):
            lat = self.enumDicts[ilat]["lattice"]
            enumLattice = Enumerate(self.enumDicts[ilat])

            if lat == 'protos':
                structures = getProtoPaths()
                for struct in structures:
                    scrambleOrder = getAllPerms(self.knary,justCyclic = 'uniqueUnaries' in struct)
                    for scramble in scrambleOrder:
                        thisCrystal = Crystal(struct,species = self.species)
                        thisCrystal.scrambleAtoms(scramble)
                        thisMTP = MTP(fittingRoot,dataSet = [thisCrystal],forRelax=True)
                        with open(path.join(fittingRoot,'to-relax.cfg'),'a+') as f:
                            f.writelines(thisMTP.lines)
                
            else:
                for struct in range(1,enumLattice.nEnumStructs+1):
                    enumLattice.generatePOSCAR(struct)
                    poscarpath = path.join(enumLattice.root,"poscar.{}.{}".format(lat,struct))
                    thisCrystal = Crystal.from_poscar(poscarpath,self.species)
                    thisMTP = MTP(fittingRoot,dataSet = [thisCrystal],forRelax=True)
                    with open(path.join(fittingRoot,'to-relax.cfg'),'a+') as f:
                        f.writelines(thisMTP.lines)

                    delpath = path.join(enumLattice.root,"poscar.{}.{}".format(lat,struct))
                    remove(delpath)
                
        thisMTP.write_relaxin()



    def writeReport(self,dset):
        import datetime
        nAtoms = len(self.crystals[0].species)
        with open('dataReport_' + dset + '.txt', 'w') as f:
            f.write(dset + ' REPORT\n')
            f.write(str(datetime.datetime.now()) + '\n')
            f.write("{:54s} {:14s}{:13s}{:14s}{:12s}{:10s}{:9s}".format("Title"," T. Energy","Enery/Atom","F. Energy","Conc.",self.crystals[0].species[0] + "-atoms",self.crystals[0].species[1] + "-atoms\n"))
            f.write('------------------------------------------------------------------------------------------------------------------\n')
            for crystal in self.crystals:
                f.write(crystal.reportline)

    def generateConvexHullPlot(self,plotAll = True):
        from scipy.spatial import ConvexHull
        from numpy import array,append
        from matplotlib import pyplot
        import matplotlib
        #with open('dataReport_VASP.txt','r') as f:
        #    lines = f.readlines()

        #del lines[0:4]
        #data = [[float(x.split()[-4]),float(x.split()[-5] )] for x in lines]
        #data = [[i.results["fEnth"],i.concentrations[0]] for x in self.crystals]
        data = [[self.concs[i],self.formationenergies[i]] for i in range(len(self.formationenergies))]
 #       print(data.shape)
        data.append([0.0,0.0])
        data.append([1.0,0.0])
        self.titles.append('pure')
        self.titles.append('pure')
        data = array(data)
#        append(data,array([ 0.0 , 0.0 ]),axis=0)
#        data = append(data,array([ 1.0 , 0.0]),axis = 0)
       # if [0.0,0.0] not in data:
       #     append(data,[0.0,0.0])
       # if [1.0,0.0] not in data:
       #     append(data,[1.0,0.0])
        print(data,'data')
        hull = ConvexHull(data)
        pyplot.plot(self.concs,self.formationenergies,'r+')
        plotConcs = []
        plotEnergies = []
#        pyplot.plot(data[hull.vertices,0], data[hull.vertices,1],'b-',lw = 2)
        print(hull.vertices, 'verts')
        print(len(data))
        vertices = sorted(hull.vertices,key = lambda k: data[k][0])
        print(len(self.titles))
        print([self.titles[x] for x in vertices])

        print(vertices,' verts')
        pyplot.figure(figsize = (15,10))
        if plotAll:
            pyplot.plot([x[0] for x in data],[x[1] for x in data],'r+')
        for ivert,vertex in enumerate(vertices):
            if data[vertex,1] <= 0:
                plotConcs.append(data[vertex,0])
                plotEnergies.append(data[vertex,1])
        pyplot.plot(plotConcs,plotEnergies,'xk-',linewidth=2.3,markersize = 8)
        font = {'family':'normal',
                    'weight': 'bold',
                    'size': 22}
        matplotlib.rc('font',**font)
        pyplot.xlabel(' Ag', fontsize = 24)
        pyplot.ylabel("Formation Energy (eV/atom)", fontsize = 24)
        pyplot.xticks(fontsize=22)
        pyplot.yticks(fontsize=22)
        pyplot.title("Convex Hull Plot")
        pyplot.savefig('chull.png')
        









                
