colored_separately=false;
x_nr_of_cells=17;
y_nr_of_cells=x_nr_of_cells;
x_cell_width=50;
y_cell_width=x_cell_width;
x_cell_border=10;
y_cell_border=x_cell_border;
x_exterior_border=20;
y_exterior_border=x_exterior_border;
cell_height=20;
panel_height=3;
strand_width=10;
strand_height=1;
support_height=1;
module_length=16;
middle_plate_height=10;
back_plate_height=10;
x_back_room_wall_thickness=10;
y_back_room_wall_thickness=x_back_room_wall_thickness;
back_room_height=50;
led_w=5;
led_h=2;

x_length = x_nr_of_cells * (x_cell_width + x_cell_border) - x_cell_border + 2*x_exterior_border;
y_length = y_nr_of_cells * (y_cell_width + y_cell_border) - y_cell_border + 2*y_exterior_border;

//* leds
for (x = [0:x_nr_of_cells-1], y = [0:y_nr_of_cells-1]) {
	translate([
			x * (x_cell_width + x_cell_border) + x_exterior_border + x_cell_width/2,
			y * (y_cell_width + y_cell_border) + y_exterior_border + y_cell_width/2,
			support_height+middle_plate_height+back_plate_height+back_room_height
			]) {
		//support
		color([1,1,1]) cube(size=[strand_width, module_length, support_height], center=true);

		//led
		translate([0, 0, led_h/2+support_height]) color([.7,.7,.7])
		cube(size=[led_w, led_w, led_h], center=true);
	}
}
//*/

//* back plate
cbp=colored_separately?[1,1,0]:[0,0,0];
color(cbp) cube([x_length, y_length, back_plate_height]);
//*/

//* back room
cbr=colored_separately?[1,0,0]:[0,0,0];
translate([0,0,back_plate_height]) color(cbr)
difference() {
	cube([x_length, y_length, back_room_height]);
	translate([x_back_room_wall_thickness, y_back_room_wall_thickness, -1])
	cube([x_length-2*x_back_room_wall_thickness, y_length-2*y_back_room_wall_thickness, back_room_height+2]);
}
//*/

//* middle panel
cmp=colored_separately?[0,1,0]:[0,0,0];
translate([0,0,back_plate_height+back_room_height]) color(cmp) 
difference() {
	cube([x_length, y_length, middle_plate_height]);
	for(x = [0:x_nr_of_cells-1], t = [y_exterior_border, y_length - y_exterior_border - strand_height]) {
		translate([
			x*(x_cell_width + x_cell_border) + x_exterior_border + 0.5*(x_cell_width - strand_width),
			t,
			-1])
		cube([strand_width, strand_height, middle_plate_height+2]);
	}
}
//*/

//* grid array
cga=colored_separately?[0,0,1]:[0,0,0];
translate([0,0,middle_plate_height+back_plate_height+back_room_height]) color(cga)
difference() {
	cube([x_length, y_length, cell_height]);
	for (x = [0:x_nr_of_cells-1], y = [0:y_nr_of_cells-1])
		translate([
			x*(x_cell_width + x_cell_border) + x_exterior_border,
			y * (y_cell_width + y_cell_border) + y_exterior_border,
			-1])
		cube([x_cell_width, y_cell_width, cell_height+2]);

	for(x = [0:x_nr_of_cells-1])
		translate([
			x*(x_cell_width + x_cell_border) + x_exterior_border + 0.5*(x_cell_width - strand_width),
			y_exterior_border + y_cell_border + 0.5*y_cell_width,
			-strand_height])
		cube([strand_width, (y_nr_of_cells-1) * (y_cell_width + y_cell_border), 2*strand_height]);
}
//*/

//* front panel
translate([0,0,cell_height+middle_plate_height+back_plate_height+back_room_height])
color([1,1,1,.3]) cube([x_length, y_length, panel_height]);
//*/
