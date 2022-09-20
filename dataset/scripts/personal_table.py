with open('personal_as_list') as f: 
	personal_as_list = [int(x) for x in f.read().splitlines()] 
with open('bgp_table_basic') as f: 
	for line in f: 
		if int(line.split()[1]) in personal_as_list: 
			print(line.strip())