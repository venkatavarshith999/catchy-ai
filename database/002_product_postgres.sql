-- Fresh v2 schema only. Not a migration of existing v1 user data.

CREATE TABLE product_counters (
	key VARCHAR(80) NOT NULL, 
	count INTEGER NOT NULL, 
	PRIMARY KEY (key)
);

CREATE TABLE product_users (
	id VARCHAR(40) NOT NULL, 
	name VARCHAR(80) NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	password VARCHAR(256) NOT NULL, 
	role VARCHAR(24) NOT NULL, 
	verified BOOLEAN NOT NULL, 
	created FLOAT NOT NULL, 
	preferences JSON NOT NULL, 
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_product_users_email ON product_users (email);

CREATE TABLE product_calls (
	id VARCHAR(40) NOT NULL, 
	user_id VARCHAR(40) NOT NULL, 
	title VARCHAR(100) NOT NULL, 
	language VARCHAR(12) NOT NULL, 
	mode VARCHAR(20) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	score INTEGER NOT NULL, 
	created FLOAT NOT NULL, 
	updated FLOAT NOT NULL, 
	retain BOOLEAN NOT NULL, 
	expires FLOAT NOT NULL, 
	count INTEGER NOT NULL, 
	transcript JSON NOT NULL, 
	evidence JSON NOT NULL, 
	warned BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES product_users (id) ON DELETE CASCADE
);

CREATE INDEX ix_product_calls_user_id ON product_calls (user_id);

CREATE INDEX ix_product_calls_expires ON product_calls (expires);

CREATE INDEX ix_product_calls_created ON product_calls (created);

CREATE TABLE product_contacts (
	id VARCHAR(40) NOT NULL, 
	owner VARCHAR(40) NOT NULL, 
	recipient VARCHAR(40), 
	name VARCHAR(80) NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	phone VARCHAR(25) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	token VARCHAR(64) NOT NULL, 
	expires FLOAT NOT NULL, 
	alerts_owner BOOLEAN NOT NULL, 
	alerts_recipient BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(owner) REFERENCES product_users (id) ON DELETE CASCADE, 
	FOREIGN KEY(recipient) REFERENCES product_users (id) ON DELETE CASCADE, 
	UNIQUE (token)
);

CREATE INDEX ix_product_contacts_recipient ON product_contacts (recipient);

CREATE INDEX ix_product_contacts_owner ON product_contacts (owner);

CREATE TABLE product_logins (
	token VARCHAR(64) NOT NULL, 
	user_id VARCHAR(40) NOT NULL, 
	expires FLOAT NOT NULL, 
	PRIMARY KEY (token), 
	FOREIGN KEY(user_id) REFERENCES product_users (id) ON DELETE CASCADE
);

CREATE INDEX ix_product_logins_user_id ON product_logins (user_id);

CREATE TABLE product_deliveries (
	id VARCHAR(40) NOT NULL, 
	owner VARCHAR(40) NOT NULL, 
	contact VARCHAR(40) NOT NULL, 
	created FLOAT NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(owner) REFERENCES product_users (id) ON DELETE CASCADE, 
	FOREIGN KEY(contact) REFERENCES product_contacts (id) ON DELETE CASCADE
);

CREATE INDEX ix_product_deliveries_contact ON product_deliveries (contact);

CREATE INDEX ix_product_deliveries_owner ON product_deliveries (owner);
