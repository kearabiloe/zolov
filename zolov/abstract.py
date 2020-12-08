import subprocess
import logging
import json
import os
import random 
import time
import re
import requests


logger = logging.getLogger(__name__)

_OPERATORS = {
	"MTN": {
		"RECHARGE":"*136*{voucher_code}#",
		"BALANCE":"*136#"
	},
	"TELKOM": {
		"RECHARGE":"*188*{voucher_code}#",
		"BALANCE":"*136#"
	},
	"VODACOM": {
		"RECHARGE":"*136*{voucher_code}#",
		"BALANCE":"*136#"
	},
	"GENERIC": {
		"RECHARGE":"{voucher_code}",
		"BALANCE":"*136#"
	}
}


class Modems():
	modems = []
	provider = 'MTN'
	balance = 0

	def __init__(self):
		self.modems = self.refresh_modems()
		return

	def ussd_run(self,string='*123#',modem=None):
		if not modem:
			#assign available modem
			modem = self.default_modem()
		self.ussd_stop(modem)
		command = subprocess.Popen(["mmcli", "--3gpp-ussd-initiate", string, "-m", modem, "--output-json" ],
			stdin =subprocess.PIPE,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			universal_newlines=True,
			bufsize=0)

		resp=command.stdout.read()
		command.stdout.close()
		#resp = json.loads(resp)
		return self.serialize_ussd_response(resp)

	def ussd_stop(self,modem=None):
		#Stop any running sesion
		if not modem:
			#assign available modem
			modem = self.default_modem()		
		command = subprocess.run(["mmcli", "--3gpp-ussd-cancel", "-m", modem, "--output-json" ])
		return command.returncode

	def balance(self,modem=None):
		if not modem:
			#assign available modem
			modem = self.default_modem()

		ussd_str = _OPERATORS[self.provider]['BALANCE']
		ussd_resp = self.ussd_run(ussd_str,modem)
		balance = float(re.findall(r'\d+.*',ussd_resp)[0])
		self.ussd_run('00',modem)
		return balance

	def refresh_modems(self):
		command = subprocess.Popen(["mmcli", "-L", "--output-json"],
		                        stdin =subprocess.PIPE,
		                        stdout=subprocess.PIPE,
		                        stderr=subprocess.PIPE,
		                        universal_newlines=True,
		                        bufsize=0)

		resp=command.stdout.read()
		command.stdout.close()
		resp = json.loads(resp)
		self.modems = resp.get('modem-list')
		return self.modems

	
	def default_modem(self):
		try:
			self.refresh_modems()
			return self.modems[0]
		except Exception as e:
			logger.warning(e)
			return None


	def serialize_ussd_response(self,response):
		resp = response.strip('USSD session initiated; new reply from network:')
		resp = resp.strip()
		return resp

class Voucher():
	data = {}
	operator = None
	modem = Modems()
	verified = False
	valid = None

	def get_remote(self):
		return {}

	def __init__(self, data={}):
		for key in data.keys():
			self.__setattr__(key,data.get(key))
		return

	def verify(self,modem=None):
		if not self.verified :
			if _OPERATORS.get(self.provider,False):
				ussd_str = _OPERATORS[self.provider]['RECHARGE'].format(voucher_code=self.voucher_code)
				ussd_resp = self.modem.ussd_run(ussd_str)
				print(ussd_resp)
				if ussd_resp.find('valid') > 0:
					#invalid voucher
					self.valid = False
				else:
					#Valid voucher. Regex match amount
					self.valid = True
			self.verified = True

		return self.valid

	def generate(self,qty=1,amount=10,bits=52,checksum=16):
		vouchers = []
		i = 0
		while i < qty:
			voucher = str(random.getrandbits(bits))
			if len(voucher) == checksum and voucher not in vouchers:
				vouchers.append({
					'voucher_code':voucher,
					'amount':amount,
					'provider':'CROWDCOIN',
					'status':'Awaiting Collection',
					'pocket_from':'/api/v1/pockets/1'
					})

				i +=1
		vouchers = [Voucher(obj) for obj in vouchers]
		return vouchers

	def generateFile(self,batch='1',ussd_code='*120*912*87*Voucher Code#',pin=None,qty=1,page_size=False):
		from PIL import Image
		from PIL import ImageFont
		from PIL import ImageDraw 
		import textwrap
		import re
		import time
		import os

		a4_points = [
			(110,190),(770,190),(1390,190),(2000,190),
			(110,1040),(770,1040),(1390,1040),(2000,1040),
			(110,1890),(770,1890),(1390,1890),(2000,1890),
			(110,2740),(770,2740),(1390,2740),(2000,2740)
		]

		a4_qrpoints = [
			(160,300),(800,300),(1440,300),(2050,300),
			(160,1160),(800,1160),(1440,1160),(2050,1160),
			(160,2020),(800,2020),(1440,2020),(2050,2020),
			(160,2850),(800,2850),(1440,2850),(2050,2850)
		]

		a3_points = [
			(730,110),(1860,110),(3080,110),
			(730,950),(1860,950),(3080,950),
			(730,1800),(1860,1800),(3080,1800),
			(730,2640),(1860,2640),(3080,2640),
			(730,3440),(1860,3440),(3080,3440),
			(730,4280),(1860,4280),(3080,4280)
		]

		a3_qrpoints = [
			(760,210),(1900,210),(3140,210),
			(760,1070),(1900,1070),(3140,1070),
			(760,1920),(1900,1920),(3140,1920),
			(760,2770),(1900,2770),(3140,2770),
			(760,3560),(1900,3560),(3140,3560),
			(760,4410),(1900,4410),(3140,4410)
		]

		if pin:
			if type(pin) == list:
				voucher_codes = pin
			else:
				voucher_codes = [pin]			
		else:
			voucher_codes = [i for i in getattr(self,'voucher_code', self.generate(qty))]
		
		page = 1
		items_per_page = 16

		a4_position = 1	

		voucher_index = 0
		results = 'batch,voucher_code,page,a4_position\n'
		
		try:
			outputdir = "output/"
			os.mkdir(outputdir)
		except FileExistsError as e:
			logger.debug(e)		
		if page_size == 'a3':
			a4_points = a3_points
			a4_qrpoints = a3_qrpoints
			items_per_page = 18

		for voucher in vouchers:
			voucher_code=voucher.voucher_code
			if a4_position > len(a4_points):
				a4_position = 1
				page +=1
			print('a4pos',a4_position)
			voucher_index +=1
			print(voucher_code)
			voucher_serial = "{batch}{page}{position}{first_four}".format(batch=batch,page=page,position=a4_position,first_four=voucher_code[:4])
			voucher_str_list = [voucher_code[i:i+4] for i in range(0, len(voucher_code), 4)]
			formated_voucher_code = ''
			for block in voucher_str_list:
				formated_voucher_code +=block+' '
			voucher_text = ussd_code.format(pin=formated_voucher_code)
			if page_size not in ['a4','a3'] :
				img = Image.open("voucher-inside-blank.png")
				draw = ImageDraw.Draw(img)
				font = ImageFont.truetype("LatoSemibold.ttf", 40)
				lines = textwrap.wrap(voucher_text, width = 34)
				current_ypos = 216
				for line in lines:
					draw.text((110, current_ypos ),line,(0,0,0),font=font)
					current_ypos += 50
				try:
					outputdir = "output/single/"
					os.mkdir(outputdir)
				except FileExistsError as e:
					logger.debug(e)					
				img.save(outputdir+'%s.png'%voucher_code)		
			else:
				# if round(voucher_index/items_per_page) <1 :
				# 	page = 1
				outputdir = 'output/batch-'+str(batch)+'/'
				try:
					os.mkdir(outputdir)
				except FileExistsError as e:
					logger.debug(e)
				output_file = outputdir+"voucher-{size}-{batch}-{page}.png".format(batch=batch,page=page,size=page_size)
				print(output_file)
				try:
					# img = Image.open(output_file)
					if a4_position == 1:
						os.remove(output_file)
					img = Image.open(output_file)
				except Exception as e:
					img = Image.open("voucher-{size}-blank.png".format(size=page_size))
				draw = ImageDraw.Draw(img)
				font = ImageFont.truetype("LatoSemibold.ttf", 25)
				voucher_font = ImageFont.truetype("LatoSemibold.ttf", 32)
				lines = textwrap.wrap(voucher_text, width = 25)
				print(a4_position)
				current_pos = a4_points[a4_position-1]
				current_line = 0
				draw.text((current_pos[0],current_pos[1]+current_line+10),ussd_code,(0,0,0),font=font)
				draw.text((current_pos[0],current_pos[1]+current_line+50),formated_voucher_code,(0,0,0),font=voucher_font)
				draw.text((current_pos[0],current_pos[1]+current_line+550),"Serial Number: "+voucher_serial,(0,0,0),font=font)
				# for textline in lines:
				# 	draw.text((current_pos[0],current_pos[1]+current_line*30),textline,(0,0,0),font=font)
				# 	current_line += 1
				qr_img = self.get_qrcode(voucher_code).resize((250,250))
				img.paste(qr_img,a4_qrpoints[a4_position-1])
				img.save(output_file)		
				img.close()
				a4_position +=1
				# page += 1
				results += "%s,%s,%s,%s\n"%(batch,voucher_code,page,a4_position)
				print('---------------')
		with open(outputdir+"RESULTS-%s.csv"%batch, "w") as fh:		
			fh.write(str(results))
			fh.close()
			
	def get_qrcode(self,data):
		import qrcode
		img = qrcode.make(data,version=1)
		return img.get_image()

class Backend():

	url = 'http://localhost:5000/api/v1/zolov/'
	api_key = '70d8d3505623671cef4bcdb6a5eb1f1d2492cae2'
	username = 'admin'	
	headers = {
		'Authorization':'ApiKey {username}:{api_key}'.format(username=username,api_key=api_key),
		'Content-type': 'application/json'
	}
	vouchers = []


	def fetch(self,url=url):
		bundle = []
		output = []
		api_call = requests.get(self.url,headers=self.headers)
		if api_call.ok:
			s = api_call.json()
			print(s.get('meta'))
			bundle = s.get('objects',[])
			self.vouchers = [Voucher(obj) for obj in bundle]
		return self.vouchers

	def post(self,vouchers=None,url=url,qty=18,amount=10):
		if not vouchers:
			# vouchers = self.fetch()
			vouchers = Voucher().generate(qty=qty,amount=amount)
		for voucher in vouchers:
			payload = voucher.__dict__
			api_call = requests.post(self.url,headers=self.headers, json=payload)
			print(api_call.json())

		return

	def print(self):
		vService = Voucher()
		vouchers = self.fetch()
		voucher_pins = []
		for v in vouchers:
			if v.status == 'Awaiting Collection':
				voucher_pins.append(v.voucher_code)
		print('Printing Vouchers X '+str(len(voucher_pins)))
		if len(voucher_pins) > 0:
			vService.generateFile(pin=voucher_pins,page_size='a3',batch='20201201A')
		return




class Operator():
	def crowdcoin_api(self):	
		return {}




def test_mtn(qty):
	dev = Modems()
	vouchers = Voucher().generate(qty)
	i=0
	    
	for v in vouchers:
		v=str(v)
		if len(v)  == 16:
			cmnd = '*136*{voucher}#'.format(voucher=v)
			resp=dev.ussd_run(cmnd)
			result = '%s,%s,%s,%s,%s\n'%(i,v,len(v),resp[0:15],time.ctime())
			with open("RESULTS.csv", "w") as fh:		
				fh.write(str(result))
			i +=1
			print(i,'{progress}% Done'.format(progress=i/qty*100))
	return

def create_pdf(batch='X202012',startpage=0,endpage=-1,outputdir='output/'):
	from PIL import Image

	imagelist = []
	directory = outputdir+batch
	print('processing: '+directory)
	for img in os.listdir(directory):
		if img.endswith('png'):
			imagelist.append(directory+"/"+img)
	imagelist.sort()
	imagelist = imagelist[startpage:endpage]
	imagelist = [Image.open(i).convert('RGB') for i in imagelist]
	# imagelist is the list with all image filenames
	print("Pages = "+str(len(imagelist)))
	pdf1_filename = directory+'/'+batch+".pdf"
	print(pdf1_filename)
	finalimagelist = []
	im1 = Image.open("voucher-back.png").convert('RGB') 
	count = 0
	for img in imagelist:
		print(img)
		if count != 0:
			finalimagelist.append(im1)
		finalimagelist.append(img)
		count =+ 1

	im1.save(pdf1_filename, "PDF" ,resolution=100.0, save_all=True, append_images=finalimagelist)