"""
An MDI Engine object.
"""

import mdi

class MDIEngine():

    boltzmann = 3.1668114e-6

    def __init__(self, engine_name, engine):
        self.engine_name = engine_name
        self.comm = engine
        self._natoms = self._get_natoms()

        try:
            self.temperature = float(self.engine_name.split("_")[1])
        except:
            self.temperature = None
        
        if self.temperature:
            self.beta = 1.0 / (self.boltzmann * self.temperature)
        else:
            self.beta = None

    def _get_natoms(self):
        mdi.MDI_Send_Command("<NATOMS", self.comm)
        return mdi.MDI_Recv(1, mdi.MDI_INT, self.comm)

    @property
    def node(self):
        # send the "<@" command to the engine to get the current node
        mdi.MDI_Send_Command("<@", self.comm) 

        # receive the name of the current node
        node_name = mdi.MDI_Recv(mdi.MDI_NAME_LENGTH, mdi.MDI_CHAR, self.comm)

        return node_name

    @node.setter
    def node(self, node_name):
        if node_name[0] != "@":
            raise ValueError("The node name must start with '@'")
        mdi.MDI_Send_Command(node_name, self.comm)
    
    @property
    def natoms(self):
        return self._natoms
    
    @natoms.setter
    def natoms(self, value):
        raise AttributeError("Cannot set the number of atoms.")
    
    @property
    def coords(self):
        mdi.MDI_Send_Command("<COORDS", self.comm)
        return mdi.MDI_Recv(self.natoms * 3, mdi.MDI_DOUBLE, self.comm)
    
    @coords.setter
    def coords(self, value):
        mdi.MDI_Send_Command(">COORDS", self.comm)
        mdi.MDI_Send(value, self.natoms * 3, mdi.MDI_DOUBLE, self.comm)

    @property
    def velocities(self):
        mdi.MDI_Send_Command("<VELOCITIES", self.comm)
        return mdi.MDI_Recv(self.natoms * 3, mdi.MDI_DOUBLE, self.comm)

    @velocities.setter
    def velocities(self, value):
        mdi.MDI_Send_Command(">VELOCITIES", self.comm)
        mdi.MDI_Send(value, self.natoms * 3, mdi.MDI_DOUBLE, self.comm)
    
    @property
    def energy(self):
        mdi.MDI_Send_Command("<ENERGY", self.comm)
        return mdi.MDI_Recv(1, mdi.MDI_DOUBLE, self.comm)
    
    @property
    def potential_energy(self):
        mdi.MDI_Send_Command("<PE", self.comm)
        return mdi.MDI_Recv(1, mdi.MDI_DOUBLE, self.comm)
    
    @property
    def cell(self):
        mdi.MDI_Send_Command("<CELL", self.comm)
        return mdi.MDI_Recv(9, mdi.MDI_DOUBLE, self.comm)
    
    @cell.setter
    def cell(self, value):
        mdi.MDI_Send_Command(">CELL", self.comm)
        mdi.MDI_Send(value, 9, mdi.MDI_DOUBLE, self.comm)
    
    def exit(self):
        mdi.MDI_Send_Command("EXIT", self.comm)

    