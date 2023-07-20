m3bolt = 3;
m3nut = 6;
m2p5bolt = 2.5;
m2p5nut = 5;

module testcube(boltd, nutd) {
  difference() {
    bh = sqrt(boltd*boltd/2);
    echo(bh);
    cube(14,center=true);
    union() {
      rotate([0,90,0]) cylinder(h=7, d=nutd, $fn=6);
      translate([-7,0,0]) rotate([45,0,0])
        cube([7,bh,bh],center=true);
      translate([-7,-4,-4]) rotate([45,0,0])
        cube([7,bh+0.4,bh+0.4],center=true);
      translate([-7,+4,-4]) rotate([45,0,0])
        cube([7,bh-0.4,bh-0.4],center=true);
    }
  }
}

module testcube2(boltd, nutd) {
  difference() {
    cube(14,center=true);
    union() {
      translate([2,0,0]) rotate([0,90,0]) cylinder(h=5, d=nutd, $fn=6);
      translate([-8,0,0]) rotate([0,90,0])
        cylinder(h=7, d=boltd, $fn=6);
      translate([-7,+4,-4]) rotate([0,90,0])
        cylinder(h=7, d=boltd-0.4, $fn=6);
      translate([-7,-4,-4]) rotate([0,90,0])
        cylinder(h=7, d=boltd+0.4, $fn=6);
    }
  }
}

testcube2(m2p5bolt, m2p5nut);
