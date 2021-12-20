# IoT PetFeeder A110118rS111909i

# system packages.
import time
import random
from datetime import datetime

# custom packages
from .osCommands import OSCommands as osc
from .AutoExecutor import AutoExecutor

# iot packages
import wiotp.sdk.device
from ibmcloudant.cloudant_v1 import CloudantV1, Document
from ibm_cloud_sdk_core.authenticators import BasicAuthenticator, authenticator

class PetFeeder:
   DEVICE_DETAILS = { # ibm device credentials.
      "identity": {
         "orgId": "cljthj",
         "typeId": "IoT_PetFeeder",
         "deviceId":"PFA110118rS111909i"
      },
      "auth": {
         "token": "12345678"
      }
   }
   
   class CLOUDANT_DETAILS: # cloudant credentials.
      username = 'apikey-v2-30cu3aik2oj2cw2mz8a030wna4fptgs9wpmgwsefxwa5'
      password = 'a4dcc4dba07cb678976d9ba42e7e23d1'
      service_url = 'https://apikey-v2-30cu3aik2oj2cw2mz8a030wna4fptgs9wpmgwsefxwa5:a4dcc4dba07cb678976d9ba42e7e23d1@813c7846-0248-4408-9017-f9e415556d98-bluemix.cloudantnosqldb.appdomain.cloud'
      database = 'pfa110118rs111909idb'
      '''Documents:
         partitioned = True
         config:timers - contains all timers.
         config:speech - contains current speech.
      '''
   
   class CONFIG: # Pet Feeder configuration.
      DEFAULT_SPEECH = "Come on, here is your meal!"
      startime = None # device startup timestamp.
      timers = None # 1-5, {
      #    1: {
      #       'time': timestamp,
      #       'active': True|False, # isEnabled?
      #       'completed': True|False, # feeded/used?
      #    },
      # }
      dispensespeech = None # speech to be played at dispense.
      
      backgroundProcess = None # Background Process Executor.
   
   client = None
   cloudantService = None

   class levels: # Storage levels.
      food = None # Food level: 0-100.
      water = None # Water level: 0-100.
   
   class CommandProcessor:
      def callback (command):
         print('\n\nPress [Enter] to clear messages ... \n\n')
         action = command.data.get('action', '')
         
         if (action.lower() == 'dispense'): # dispense food & water.
            PetFeeder.dispense()
         elif (action.lower() == 'speak'): # speak speech.
            PetFeeder.speak(
               (
                  command.data.get('speech') or (
                     PetFeeder.CONFIG.dispensespeech
                     or PetFeeder.CONFIG.DEFAULT_SPEECH
                  )
               ),
            )
         elif (action.lower() == 'upload'): # upload levels to ibm.
            PetFeeder.CommandProcessor.upload()
         elif (action.lower() == 'update'): # download config from cloudant.
            updatepart = None
            try:
               updatepart = int(command.data.get('updatepart', 0))
               if (updatepart not in (0, 1, 2)):
                  raise ValueError()
            except:
               print(
                  "CommandProcessor:: callback: update - "
                  + "Invalid updatepart '{0}'!".format(
                     command.data.get('updatepart'),
                  )
               )
               return None
            PetFeeder.CommandProcessor.update(updatepart)
         elif (action.lower() == 'uploadconfig'): # upload config to cloudant.
            uploadpart = None
            try:
               uploadpart = int(command.data.get('uploadpart', 0))
               if (uploadpart not in (0, 1, 2)):
                  raise ValueError()
            except:
               print(
                  "CommandProcessor:: callback: uploadconfig - "
                  + "Invalid uploadpart '{0}'!".format(
                     command.data.get('uploadpart'),
                  )
               )
               return None
            PetFeeder.CommandProcessor.uploadconfig(uploadpart)
         elif (action.lower() == 'settimer'): # set timers.
            timerNumber = None
            try:
               timerNumber = int(command.data.get('timer', 1))
               if (timerNumber not in (1, 2, 3, 4, 5)):
                  raise ValueError()
            except:
               print(
                  "CommandProcessor:: callback: settimer - "
                  + "Invalid timer '{0}'!".format(
                     command.data.get('timer'),
                  )
               )
               return None
            timerhour = None
            try:
               timerhour = int(command.data.get('hour', 0))
               if (timerhour not in range(0, 24,)):
                  raise ValueError()
            except:
               print(
                  "CommandProcessor:: callback: settimer - "
                  + "Invalid hour '{0}'!".format(
                     command.data.get('hour'),
                  )
               )
               return None
            timerminute = None
            try:
               timerminute = int(command.data.get('minute', 0))
               if (timerminute not in range(0, 60,)):
                  raise ValueError()
            except:
               print(
                  "CommandProcessor:: callback: settimer - "
                  + "Invalid minute '{0}'!".format(
                     command.data.get('minute'),
                  )
               )
               return None
            timerEnabled = None
            try:
               timerEnabled = str(command.data.get(
                  'enabled', '0'
               ))
               if (timerEnabled not in ('0', '1',)):
                  raise ValueError()
               
               timerEnabled = int(timerEnabled)
            except:
               print(
                  "CommandProcessor:: callback: settimer - "
                  + "Invalid time '{0}'!".format(
                     command.data.get('enabled'),
                  )
               )
               return None
            PetFeeder.CommandProcessor.settimer(
               timerNumber,
               timerhour,
               timerminute,
               timerEnabled,
            )
         elif (action.lower() == 'setdispensespeech'): # set speech.
            PetFeeder.CONFIG.dispensespeech = command.data.get('speech') or (
               PetFeeder.CONFIG.dispensespeech
               or PetFeeder.CONFIG.DEFAULT_SPEECH
            )
            PetFeeder.CommandProcessor.uploadconfig(2) # save speech to cloud.
         elif (action.lower() == 'command'): # custom commands.
            print(
               "CommandProcessor:: Callback: Recieved command '{0}'!".format(
                  command.data.get('command', '--'),
               )
            )
         else: # unrecognized commands.
            print(
               "CommandProcessor:: Callback: Unrecognized action '{0}'!".format(
                  action,
               )
            )
      
      def upload (): # uploads food & water levels to ibm cloud.
         try:
            PetFeeder.client.publishEvent(
               eventId='status',
               msgFormat='json',
               qos=0,
               onPublish=None,
               data={
                  'levels': {
                     'food': PetFeeder.levels.food,
                     'water': PetFeeder.levels.water,
                  },
               },
            )
            print('CommandProcessor:: Upload: Success!')
         except Exception as exception:
            print(
               'CommandProcessor:: Upload: Error - {0}!'.format(
                  exception,
               )
            )
      
      def update (updatepart=0): # downloads config from cloudant.
         if (updatepart in (0, 1)):
            try:
               timerDocument = PetFeeder.cloudantService.get_document(
                  db=PetFeeder.CLOUDANT_DETAILS.database,
                  doc_id='config:timers'
               ).get_result()
               
               PetFeeder.CONFIG.timers = dict([
                  (
                     tindex,
                     {
                        'time': (
                           datetime.now().replace(
                              hour=(
                                 datetime.strptime(
                                    str(
                                       timerDocument['timers'][str(tindex)][(
                                          'time'
                                       )]
                                    ),
                                    '%H:%M',
                                 ).hour
                              ),
                              minute=(
                                 datetime.strptime(
                                    str(
                                       timerDocument['timers'][str(tindex)][(
                                          'time'
                                       )]
                                    ),
                                    '%H:%M',
                                 ).minute
                              ),
                              second=0
                           )
                        ),
                        'active': (
                           timerDocument['timers'][str(tindex)]['active']
                        ),
                        'completed': (
                           False
                           if (
                              (
                                 datetime.now().replace(
                                    hour=(
                                       datetime.strptime(
                                          str(
                                             timerDocument['timers'][str(
                                                tindex
                                             )]['time']
                                          ),
                                          '%H:%M',
                                       ).hour
                                    ),
                                    minute=(
                                       datetime.strptime(
                                          str(
                                             timerDocument['timers'][str(
                                                tindex
                                             )]['time']
                                          ),
                                          '%H:%M',
                                       ).minute
                                    ),
                                    second=0
                                 )
                                 - datetime.now()
                              ).total_seconds() > -60
                           )
                           else
                           True
                        ),
                     },
                  )
                  for tindex in range(1, 6)
               ])
               print('CommandProcessor:: Update: Timer update Success!')
            except Exception as exception:
               print(
                  'CommandProcessor:: Update: '
                  + 'Timer update Error - {0}!'.format(
                     exception,
                  )
               )
         
         if (updatepart in (0, 2)):
            try:
               speechDocument = PetFeeder.cloudantService.get_document(
                  db=PetFeeder.CLOUDANT_DETAILS.database,
                  doc_id='config:speech'
               ).get_result()
               
               PetFeeder.CONFIG.dispensespeech = str(speechDocument['speech'])
               
               print('CommandProcessor:: Update: Speech update Success!')
            except Exception as exception:
               print(
                  'CommandProcessor:: Update: '
                  + 'Speech update Error - {0}!'.format(
                     exception,
                  )
               )
      
      def uploadconfig (uploadpart=0): # uploads config to cloudant.
         if (uploadpart in (0, 1)):
            oldtimerdocument = None
            try:
               oldtimerdocument = PetFeeder.cloudantService.get_document(
                  db=PetFeeder.CLOUDANT_DETAILS.database,
                  doc_id='config:timers',
               ).get_result()
               print('CommandProcessor:: UploadConfig: Timer GET Success!')
            except Exception as exception:
               print(
                  'CommandProcessor:: UploadConfig: Timer GET '
                  + 'Error - {0}!'.format(
                     exception,
                  )
               )
            
            try:
               timerdocument = Document(
                  id='config:timers',
                  rev=oldtimerdocument['_rev'],
                  timers=dict([
                     (
                        str(index),
                        {
                           'time': datetime.strftime(
                              PetFeeder.CONFIG.timers[index]['time'],
                              '%H:%M',
                           ),
                           'active': PetFeeder.CONFIG.timers[index]['active'],
                        },
                     )
                     for index in range(1, 6)
                  ])
               )
               response = PetFeeder.cloudantService.post_document(
                  db=PetFeeder.CLOUDANT_DETAILS.database,
                  document=timerdocument,
               ).get_result()
               print('CommandProcessor:: UploadConfig: Timer upload Success!')
            except Exception as exception:
               print(
                  'CommandProcessor:: UploadConfig: Timer upload '
                  + 'Error - {0}!'.format(
                     exception,
                  )
               )
         
         if (uploadpart in (0, 2)):
            oldspeechdocument = None
            try:
               oldspeechdocument = PetFeeder.cloudantService.get_document(
                  db=PetFeeder.CLOUDANT_DETAILS.database,
                  doc_id='config:speech',
               ).get_result()
               print('CommandProcessor:: UploadConfig: Speech GET Success!')
            except Exception as exception:
               print(
                  'CommandProcessor:: UploadConfig: Speech GET'
                  + 'Error - {0}!'.format(
                     exception,
                  )
               )
            
            try:
               speechdocument = Document(
                  id='config:speech',
                  rev=oldspeechdocument['_rev'],
                  speech=PetFeeder.CONFIG.dispensespeech,
               )
               response = PetFeeder.cloudantService.post_document(
                  db=PetFeeder.CLOUDANT_DETAILS.database,
                  document=speechdocument,
               ).get_result()
               print('CommandProcessor:: UploadConfig: Speech upload Success!')
            except Exception as exception:
               print(
                  'CommandProcessor:: UploadConfig: Speech upload '
                  + 'Error - {0}!'.format(
                     exception,
                  )
               )
      
      def settimer (timerNumber, timerhour, timerminute, timerEnabled):
         # sets specified timer and calls uploadconfig.
         PetFeeder.CONFIG.timers[timerNumber]['time'] = datetime.now().replace(
            hour=int(timerhour),
            minute=int(timerminute),
            second=0,
         )
         PetFeeder.CONFIG.timers[timerNumber]['active'] = (
            True
            if (timerEnabled == 1)
            else
            False
         )
         
         timeDuration = (
            PetFeeder.CONFIG.timers[timerNumber]['time']
            - datetime.now()
         ).total_seconds()
         
         PetFeeder.CONFIG.timers[timerNumber]['completed'] = (
            False
            if (timeDuration > -60)
            else
            True
         )
         
         PetFeeder.CommandProcessor.uploadconfig(1)
   
   def connect (): # connects iot to ibm and cloudant cloud services.
      PetFeeder.client = wiotp.sdk.device.DeviceClient(
         config=PetFeeder.DEVICE_DETAILS,
         logHandlers=None,
      )
      PetFeeder.client.connect()
      PetFeeder.client.commandCallback = PetFeeder.CommandProcessor.callback
      
      PetFeeder.cloudantService = CloudantV1(
         authenticator=BasicAuthenticator(
            PetFeeder.CLOUDANT_DETAILS.username,
            PetFeeder.CLOUDANT_DETAILS.password,
         ),
      )
      PetFeeder.cloudantService.set_service_url(
         PetFeeder.CLOUDANT_DETAILS.service_url,
      )
   
   def disconnect (): # disconnects from cloud services.
      PetFeeder.client.disconnect()
   
   def refill (food=None, water=None): # refills food & water over existing.
      if (type(food).__name__ == 'int'):
         if (food == 0):
            PetFeeder.levels.food = 0
         else:
            PetFeeder.levels.food += int(food)
         
         if (PetFeeder.levels.food >= 100): # max 100.
            PetFeeder.levels.food = 100
         elif (PetFeeder.levels.food < 0): # min 0.
            PetFeeder.levels.food = 0
      
      if (type(water).__name__ == 'int'):
         if (water == 0):
            PetFeeder.levels.water= 0
         else:
            PetFeeder.levels.water += int(water)
         
         if (PetFeeder.levels.water >= 100): # max 100.
            PetFeeder.levels.water = 100
         elif (PetFeeder.levels.water < 0): # min 0.
            PetFeeder.levels.water = 0
      
      print('PetFeeder:: Refill: Status - food={0}; water={1}.'.format(
            PetFeeder.levels.food,
            PetFeeder.levels.water,
         )
      )
   
   def dispense (): # dispenses food & water and plays speech.
      fooddispensed = False
      waterdispensed = False
      if (PetFeeder.levels.food > 10):
         PetFeeder.levels.food -= 1
         fooddispensed = True
         print('PetFeeder:: Dispenser: Food dispensed!')
      elif ((PetFeeder.levels.food > 0) and (PetFeeder.levels.food <= 10)):
         PetFeeder.levels.food -= 1
         fooddispensed = True
         print('PetFeeder:: Dispenser: Food dispensed!')
         PetFeeder.notify('Low on food!') # notify user of low food level.
      else:
         print('PetFeeder:: Dispenser: No food!')
         PetFeeder.notify('No food in dispenser!') # no food notification.
      
      if (PetFeeder.levels.water > 10):
         PetFeeder.levels.water -= 1
         waterdispensed = True
         print('PetFeeder:: Dispenser: Water dispensed!')
      elif ((PetFeeder.levels.water > 0) and (PetFeeder.levels.water <= 10)):
         PetFeeder.levels.water -= 1
         waterdispensed = True
         print('PetFeeder:: Dispenser: Water dispensed!')
         PetFeeder.notify('Low on water!') # notify user of low water level.
      else:
         print('PetFeeder:: Dispenser: No water!')
         PetFeeder.notify('No water in dispenser!') # no water notification.
      
      if (fooddispensed or waterdispensed): # play speech if dispensed.
         PetFeeder.speak((
            PetFeeder.CONFIG.dispensespeech
            or PetFeeder.CONFIG.DEFAULT_SPEECH
         ))
      
      PetFeeder.CommandProcessor.upload() # upload food & water levels.
   
   def speak (text=None): # speaks to pet.
      print(
         'PetFeeder:: Speaker: Owner - {0}.'.format(
            text or PetFeeder.CONFIG.dispensespeech
            or PetFeeder.CONFIG.DEFAULT_SPEECH
         )
      )
   
   def notify (text): # sends a notification to user.
      try:
         PetFeeder.client.publishEvent(
            eventId='notification',
            msgFormat='json',
            qos=0,
            onPublish=None,
            data={
               'alert': text,
            },
         )
         print('PetFeeder:: Notify: Success!')
      except Exception as exception:
         print(
            'PetFeeder:: Notify: Error - {0}!'.format(
               exception,
            )
         )
   
   def reCalliberate (): # re-calliberates timers.
      PetFeeder.CONFIG.starttime = datetime.now()
      
      for index in range(1, 6):
         CommandProcessor.settimer(
            index,
            datetime.strftime(
               PetFeeder.CONFIG.timers[index]['time'],
               '%H:%M',
            ),
            (
               1
               if (PetFeeder.CONFIG.timers[index]['active'] == True)
               else
               0
            ),
         )
   
   def autoFeeder (): # Code for background process.
      instructed = False
      
      if (
            divmod(
               (
                  PetFeeder.CONFIG.starttime
                  - datetime.now()
               ).total_seconds(),
               3600,
            )[0] <= -24
         ):
         print('\n\nPress [Enter] to clear messages ... \n\n')
         instructed = True
         PetFeeder.reCalliberate()
      
      for index, timer in PetFeeder.CONFIG.timers.items():
         if (
               (timer['active'] == True)
               and (timer['completed'] == False)
               and (
                  (timer['time'] - datetime.now()).total_seconds() <= 0
               )
            ):
            timer['completed'] = True
            if (not instructed):
               instructed = True
               print('\n\nPress [Enter] to clear messages ... \n\n')
            
            PetFeeder.dispense()
            continue
   
   def run (): # main callable.
      PetFeeder.connect()
      
      PetFeeder.CONFIG.starttime = datetime.now()
      PetFeeder.CommandProcessor.update(0)
      PetFeeder.CommandProcessor.uploadconfig(1)
      
      PetFeeder.levels.food = random.randint(15, 35)
      PetFeeder.levels.water = random.randint(15, 35)
      
      PetFeeder.CommandProcessor.upload()
      
      PetFeeder.CONFIG.backgroundProcess = AutoExecutor( # background process.
         exec_function=PetFeeder.autoFeeder,
         runType='thread',
         interval=60,
         daemon=True,
      )
      
      try:
         PetFeeder.CONFIG.backgroundProcess.start()
         
         PetFeeder.cli_executor()
      except:
         print('\nExiting ...')
      finally:
         PetFeeder.disconnect()
         osc.CLEAR()
         print(
            '! Thanks for using IoT Automatic Pet Feeder !\n\n'
            + '-----------------------------------------\n'
            + '------: Designed and developed by :------\n'
            + '*************: Arunesh Gour :************\n'
            + '*************: Sahil Saini  :************\n'
            + '------------------------------------------\n'
         )
         exit(0)
   
   def cli_executor (): # cli loop.
      osc.CLEAR()
      print(
         '! Welcome to IoT Automatic Pet Feeder !\n\n'
         + '-----------------------------------------\n'
         + '------: Designed and developed by :------\n'
         + '*************: Arunesh Gour :************\n'
         + '*************: Sahil Saini  :************\n'
         + '------------------------------------------\n'
         + '\n\nLoading ...\n'
      )
      time.sleep(1.2)
      
      while True:
         osc.CLEAR()
         print('IoT Automatic Pet Feeder\n')
         
         print('[I]: Pet Feeder is running in background.\n')
         print(
            'Levels:: Food: {0}; Water: {1}.\n\n'.format(
               PetFeeder.levels.food,
               PetFeeder.levels.water,
            )
            + '{0}: Press [Enter] to clear any unwanted messages :{0}'.format(
               ('-'*15),
            )
            + '\n'
         )
         choice = input('What to do? (u-upload|d-dispense|r-refill|q-quit): ')
         
         if (
               choice.replace(' ', '').lower() in (
                  'u', 'upload',
               )
            ):
            print('')
            PetFeeder.CommandProcessor.upload()
            print('Wait ...')
            time.sleep(1.5)
         elif (
               choice.replace(' ', '').lower() in (
                  'd', 'dispense',
               )
            ):
            print('')
            PetFeeder.dispense()
            print('Wait ...')
            time.sleep(1.5)
         elif (
               choice.replace(' ', '').lower() in (
                  'r', 'refill', '1', 'f', 'fill',
               )
            ):
            print('')
            PetFeeder.refill(
               random.randint(5, 15),
               random.randint(5, 15),
            )
            print('Wait ...')
            time.sleep(1.5)
         elif (
               choice.replace(' ', '').lower() in (
                  'q', 'quit', '0', '-1', 'e', 'exit', 'x',
               )
            ):
            try:
               PetFeeder.CONFIG.backgroundProcess.kill()
            except:
               pass
            
            return None
         elif (
               choice.replace(' ', '').lower() in (
                  'a', 'author', 'dev', 'devs', 'developer', 'designer',
                  'developers', 'designers', 'i', 'info', 'inventor',
                  'information', 'data', 'creds', 'credit', 'credits',
                  'who', 'whoami', 'makers', 'maker', 'authors',
                  'inventors', 'cred',
               )
            ):
            osc.CLEAR()
            print(
               '! IoT Automatic Pet Feeder !\n\n'
               + '-----------------------------------------\n'
               + '------: Designed and developed by :------\n'
               + '*************: Arunesh Gour :************\n'
               + '*************: Sahil Saini  :************\n'
               + '------------------------------------------\n'
               + '\n[I]: Pet Feeder is running in background.\n'
            )
            input('Press [Enter] to continue ... ')
            continue
         else:
            print('\nWait ...')
            time.sleep(0.8)
            continue
      
      return None

if __name__ == '__main__':
   PetFeeder.run()
