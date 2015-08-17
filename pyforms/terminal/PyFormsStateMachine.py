import sys, glob, os
import pyforms.Utils.tools as tools, time
import argparse
from pyforms.terminal.BaseWidget import BaseWidget

from pyStateMachine.States.State import State
from pyStateMachine.StateMachineControllers.StatesController import StatesController


def gotoAppState(true=None, false=None, trueParms={}, falseParms={}):
	def go2decorator(func):
		def func_wrapper(self, inVar): return func(self, inVar)

		func_wrapper.trueParms 		= trueParms
		func_wrapper.falseParms 	= falseParms
		func_wrapper.go2StateTrue  	= true
		func_wrapper.go2StateFalse 	= false
		func_wrapper.label = func.__name__ if func.__doc__==None else '\n'.join([x for x in func.__doc__.replace('\t','').split('\n') if len(x)>0])
		return func_wrapper
	return go2decorator


class PyFormsState(State):

	
	def run(self, inVar):
		if hasattr(self,'_application'):  self._application.executeEvents()
		return super(PyFormsState, self).run(inVar)


class PyFormsStateMachine(StatesController, BaseWidget):

	_parser = argparse.ArgumentParser()
	

	def __init__(self, title):
		BaseWidget.__init__(self, title)
		StatesController.__init__(self, self.STATES)		
		
		for fromStateName, state in self.states.items():
			if hasattr(state,'APP_CLASS'):
				# Add the instance of the application to the State machine node
				app 				= state.APP_CLASS(); 
				app._parser 		= self._parser
				app._controlsPrefix = fromStateName
				state._application 	= app 	
				

	def initForm(self):

 		apps 	 	   		= {}
 		self._paramsFlow 	= {}
 		self._initalParms	= {}
 		self._appsOutParams = {}

 		# Load the applications
		for fromStateName, state in reversed( self.states.items() ):
			if hasattr(state,'APP_CLASS'):
				# Add the instance of the application to the State machine node
				app = state._application
				app.initForm(parse=False);
		
		self._parser.add_argument(
			"--exec", default='', 
			help='Function from the application that should be executed. Use | to separate a list of functions.')
		
		self._args = self._parser.parse_args()

		for fromStateName, state in reversed( self.states.items() ):
			if hasattr(state,'APP_CLASS'):
				app 		= state._application
				app._args 	= self._args
				app.parseTerminalParameters()	

		for function in self._args.__dict__.get("exec", []).split('|'):
			if len(function)>0:
				getattr(self, function)()

 		
	def iterateStates(self):
		"""
		Iterate states - each call go to another level
		"""
		if len(self._waitingStates)>0:
			statesOutputs = []

			for fromStateName, toStateName, inputParam in self._waitingStates:
				state = self._states[toStateName]
				if hasattr(state,'APP_CLASS'):
					app = state.APP_CLASS(); 
					state._application = app
					state._application.initForm(parse=False)
					app._args 	= self._args
					app.parseTerminalParameters()	

					# Initiante the application with the default values set by the user
					for controlName, controlValue in self._initalParms[toStateName].items():
						getattr(state._application, controlName).value = controlValue

					if toStateName in self._paramsFlow:
						for inParm, outParam in self._paramsFlow[toStateName][fromStateName].items():
							state._application.formControls[inParm].value = self._appsOutParams[outParam]
					else:
						print "no params found for", toStateName


			#First run all the pending states
			for fromStateName, toStateName, inputParam in self._waitingStates:
				state = self._states[toStateName]
				statesOutputs.append( (toStateName ,state, state.run(inputParam) ) )



			#Check the events of each exectuted state:
			for stateName, state, output in statesOutputs:

				if hasattr(state,'_application'):
					for controlName, control in state._application.formControls.items():
						self._appsOutParams['{0}.{1}'.format(stateName, controlName)] = control.value

				#Remove the exectued state from the waiting queue
				self._waitingStates.pop(0) 

				#Check each event
				for e in state.events:
					#Select the next state to go
					go2State = e.go2StateTrue if e(state, output) else e.go2StateFalse

	 				
					#In case the state is None, it stops the state execution
					if go2State!=None: 
						self._waitingStates.append( [stateName, go2State, output] )
					else:
						self._waitingStates.append( [stateName, 'EndState', output] )

		else:
			print "State machine ended"



	def execute(self): 
		apps 	 	   		= {}
 		inParams 	   		= {}


		# Load the applications
		for fromStateName, state in reversed( self.states.items() ):
			if hasattr(state,'APP_CLASS'):
				
				for e in state.events:
	 				for paramIn, paramOut in e.trueParms.items():
	 					#For each event define the flow of parameters

	 					if e.go2StateTrue not in self._paramsFlow:  
	 						self._paramsFlow[e.go2StateTrue] = {}
	 					if paramIn 		  not in self._paramsFlow[e.go2StateTrue]:  
	 						self._paramsFlow[e.go2StateTrue][fromStateName] = {}

	 					paramState, stateParam = paramIn.split('.')
	 					self._paramsFlow[e.go2StateTrue][fromStateName][stateParam] = paramOut
	 					

		self._appsOutParams = {}

		
		# Save the parameters set by the user
		for stateName, state in reversed( self.states.items() ):
			if hasattr(state, '_application'):
				self._initalParms[stateName] = {}
				for controlName, control in state._application.formControls.items():
					self._initalParms[stateName][controlName] = control.value
			
		while not self.ended: self.iterateStates()

		
	def eventExtraComment(self, e, result):
		if result:
			if len(e.trueParms)>0: 
				res = ""
				for inparam, outparam in e.trueParms.items():
					inStateName, inParamName = inparam.split('.')
					outStateName, outParamName = outparam.split('.')

					inParamName = self.states[inStateName]._application.formControls[inParamName].label
					outParamName = self.states[outStateName]._application.formControls[outParamName].label
					res += '{0}::{1}={2}::{3}\n'.format(inStateName, inParamName, outStateName, outParamName)
				return res
			else:
				return None
		else:
			if len(e.falseParms)>0:
				for inparam, outparm in e.falseParms.items():
					inParamName = self.states[inStateName]._application.formControls[inParamName].label
					outParamName = self.states[outStateName]._application.formControls[outParamName].label
					res += '{0}::{1}={2}::{3}\n'.format(inStateName, inParamName, outStateName, outParamName)
				return res
			else:
				return None



def startApp(states):
	app = QtGui.QApplication(sys.argv)
	container = Container(states)
	app.exec_()