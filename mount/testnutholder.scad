squarenuthead=7;
squarenutthickness=2;
boltdiam=4.5;
bolthead=8;
boltheadt=4;
margin=4;
block=squarenuthead+margin;
$fn=100;

union() {
  difference() {
    cube(block,center=true);
    union() {
      cylinder(h=block, d=boltdiam, center=true);
      translate([0,0,block/2-boltheadt/2])
        cylinder(h=boltheadt, d=bolthead, center=true);
      translate([0,0,-block/2+squarenutthickness/2])
        cube([squarenuthead,squarenuthead,squarenutthickness],center=true);
    }
  }
  // support monolayer
  translate([0,0,-block/2+squarenutthickness+0.1])
      color("red") cube([block,block,0.2], center=true);
}