squarenuthead=7;
squarenutthickness=4+5; // includes margin
boltdiam=4.5;
bolthead=8.5;
boltheadt=4;
boltlen=32; // 30mm + 2mm margin
margin=4;
block=squarenuthead+margin;
monolayer_h=0.2;
mount_d=32;
mount_x=54;
mount_y=24;
mount_z=mount_d+12;
boltoffset_x=11.5;
boltoffset_y=10;
mountoffset=24;
bolt_inset=mount_z-boltlen; // bolt head inset this far from bottom 

module mount() { 
  union() {
    difference() {
      cube([mount_x,mount_y,mount_z],center=true);
      union() {
        // hole for stem
        rotate([90,0,0])
          cylinder(h=mount_y+2, d=mount_d, center=true, $fn=600);
        // separator between top and bottom
        cube([mount_x+2,mount_y+2,1],center=true);
        // holes for wires
        for(x=[-(mount_x-boltoffset_x)/2, (mount_x-boltoffset_x)/2])
          translate([x,0,0])
            cube([6,4.5,mount_z+2],center=true);
        // holes for joining bolts+nuts
        for(x=[-(mount_x-boltoffset_x)/2, (mount_x-boltoffset_x)/2])
          for(y=[-(mount_y-boltoffset_y)/2, (mount_y-boltoffset_y)/2])
            translate([x,y,0])
              union() {
                cylinder(h=mount_z+2, d=boltdiam, center=true, $fn=100);
                translate([0,0,mount_z/2-squarenutthickness/2])
                  cube([squarenuthead,squarenuthead,squarenutthickness], center=true);
                translate([0,0,mount_z/2-boltlen-bolt_inset/2])
                  cylinder(h=bolt_inset, d=bolthead, center=true, $fn=100);
        
                }
        // mount holes
        for(x=[-mountoffset/2, mountoffset/2])
          translate([x,0,0])
          union() {
            cylinder(h=mount_z+1, d=boltdiam, center=true,$fn=100);
            cube([squarenuthead,squarenuthead,mount_z-4], center=true);
          }
      }
    }
    for(x=[-(mount_x-boltoffset_x)/2, (mount_x-boltoffset_x)/2])
      for(y=[-(mount_y-boltoffset_y)/2, (mount_y-boltoffset_y)/2]) {
        mono_d=bolthead+1;
        translate([x,y,mount_z/2-squarenutthickness-monolayer_h/2])
          color("red")
            cube([mono_d,mono_d,monolayer_h],center=true);
        translate([x,y,mount_z/2-boltlen+monolayer_h/2])
          color("red")
            cube([mono_d, mono_d,monolayer_h],center=true);
        }
  }
}


module mount_separator(remove=0) { // remove=1=top, -1=bottom, 0=nothing
  difference() {
    mount();
    // remove top/bottom
    if(remove!=0)
      translate([0,0,remove*50])
        cube([100,100,100],center=true);
  }
}


module box_with_corners(size_x,size_y,corner_r,thickness) {
  t=thickness;
  union() {
    c_x=size_x/2-corner_r;
    c_y=size_y/2-corner_r;
    for(x=[-c_x,c_x])
      for(y=[-c_y,c_y])
        translate([x,y,0])
          cylinder(h=t, r=corner_r, center=true,$fn=100);
    cube([size_x,size_y-corner_r*2,t],center=true);
    cube([size_x-corner_r*2,size_y,t],center=true);
  }
}

module badger_outline() {
  t=10; // badger thickness
  corner_r=2.9;
  size_x=85.6;
  size_y=48.7;
  box_with_corners(size_x,size_y,corner_r,t);
}

module badger_lower_box() {
  t=10; // badger thickness
  w=2; // wall thickness
  bh=3; // bolt head height
  wb=w+bh; // base thickness including 3mm for bolt head
  corner_r=3;
  size_x=86;
  size_y=49;
  difference() {
    box_with_corners(size_x+w*2,size_y+w*2,corner_r+w,t+wb);
    union() {
      translate([0,0,wb/2])
        box_with_corners(size_x,size_y,corner_r,t);
      // holes for wires
      for(x=[-(mount_x-boltoffset_x)/2, (mount_x-boltoffset_x)/2])
        translate([x,0,0])
          cube([6,4.5,t+wb*2],center=true);
      // mount holes
      for(x=[-mountoffset/2, mountoffset/2])
        translate([x,0,-wb/2])
        union() {
          cylinder(h=t+wb+1, d=boltdiam, center=true,$fn=50);
          cylinder(h=t-bh, d=bolthead, center=true, $fn=100);
        }
    }
  }
}

module badger_upper_box() {
  t=10+5; // badger thickness + thickness of base
  w=2; // wall thickness
  lh=0.2; // layer height
  screen_w=3; // screen thickness
  frame_w=1;  // thickness of frame around screen
  frame_s=7+8;  // frame size
  corner_r=3;
  gap=0.4;
  size_x=86+gap;
  size_y=49+gap;
  difference() {
    //box_with_corners(size_x+w*4,size_y+w*4,corner_r+w*2,t+screen_w+frame_w);
    
    union() {
      translate([0,0,-w/2])
      for(stp=[0:lh:w])
        translate([0,0,stp])
          box_with_corners(size_x+w*4-stp*2,size_y+w*4-stp*2,corner_r+w*2+gap-stp,t+screen_w+frame_w-w);
    }
    union() {
      translate([0,0,-(screen_w+frame_w)/2])
        box_with_corners(size_x+w*2,size_y+w*2,corner_r+w,t);
      translate([0,0,-frame_w/2])
        box_with_corners(size_x,size_y,corner_r,t+screen_w);
      box_with_corners(size_x-frame_s,size_y-frame_s,corner_r,t+screen_w+frame_w);
    }
  }
}

module psu_lower_box() {
  t=34; // lid
  w=2; // wall thickness
  corner_r=3;
  size_x=86;
  size_y=49;
  difference() {
    box_with_corners(size_x+w*2,size_y+w*2,corner_r+w,t+w);
    union() {
      translate([0,0,w/2])
        box_with_corners(size_x,size_y,corner_r,t);
    }
  }
  //TODO: add bolt points
}


module psu_upper_box() {
  t=12; // lid
  w=2; // wall thickness
  bh=3; // bolt head height
  wb=w+bh; // base thickness including 3mm for bolt head
  corner_r=3;
  gap=0.4;
  size_x=86+gap;
  size_y=49+gap;
  rotate([180,0,0])
  difference() {
    box_with_corners(size_x+w*4,size_y+w*4,corner_r+w*2+gap,t+wb);
    union() {
      translate([0,0,wb/2])
        box_with_corners(size_x+w*2,size_y+w*2,corner_r+w+gap,t);
      // holes for wires
      for(x=[-(mount_x-boltoffset_x)/2, (mount_x-boltoffset_x)/2])
        translate([x,0,0])
          cube([6,4.5,t+wb*2],center=true);
      // mount holes
      for(x=[-mountoffset/2, mountoffset/2])
        translate([x,0,-wb/2])
        union() {
          cylinder(h=t+wb+1, d=boltdiam, center=true,$fn=50);
          cylinder(h=t-bh, d=bolthead, center=true, $fn=100);
        }
    }
  }
}


// battery:
//   37mm wide, 70mm long, 19mm deep
// circuit board
//   12mm deep
// capacitor:
//   18mm diameter, 41mm long inc wires


// model
//  0 = all
//  1 = mount lower
//  2 = mount upper
//  3 = badger lower
//  4 = badger upper
//  5 = psu upper (lid)
//  6 = psu lower (main box)

model=56;
if(model==0) {
  mount_separator(0);
  translate([0,0,31])
      union() {
        badger_lower_box();
        //color("green") badger_outline();
    }
  translate([0,0,50])
    badger_upper_box();
  translate([0,0,-32])
    psu_upper_box();
  translate([0,0,-55])
    psu_lower_box();
}
if(model==1)
  mount_separator(1);
if(model==2)
  rotate([180,0,0]) mount_separator(-1);
if(model==3)
  badger_lower_box();
if(model==4)
  rotate([180,0,0]) badger_upper_box();
if(model==5)
  rotate([180,0,0]) psu_upper_box();
if(model==6)
  psu_lower_box();
if(model==56) {
  psu_lower_box();
  translate([0,0,28]) psu_upper_box();
}