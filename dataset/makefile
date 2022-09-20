all: personal_as_list bgp_table_basic personal_as_table ampr_table_basic ampr_as_list ases_of_interest as_upstreams

personal_as_list:
	curl -A "Contact: noc@ewpratten.com" https://bgp.tools/tags/perso.csv | cut -d',' -f1 | cut -d'S' -f2 | sort -n | uniq > $@

bgp_table_basic:
	curl -A "Contact: noc@ewpratten.com" https://bgp.tools/table.txt | sort -n | uniq > $@

personal_as_table: bgp_table_basic personal_as_list scripts/personal_table.py
	python3 scripts/personal_table.py > $@

ampr_table_basic: bgp_table_basic
	cat bgp_table_basic | grep "^44\." | grep -v 16509 | sort -n > $@

ampr_as_list: ampr_table_basic
	cat ampr_table_basic | cut -d' ' -f2 | sort -n | uniq > $@

ases_of_interest: personal_as_list ampr_as_list
	cat personal_as_list ampr_as_list | sort -n | uniq > $@

# ripe_ris.gz:
# 	curl "https://data.ris.ripe.net/rrc00/$(shell date +%Y.%m)/bview.$(shell date +%Y%m%d).0000.gz" -o $@

# raw_upstream_connections: ripe_ris.gz
# 	python3 scripts/upstream_list.py > $@

as_upstreams: ases_of_interest
	python3 scripts/relationships.py