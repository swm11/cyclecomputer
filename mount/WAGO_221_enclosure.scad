// WAGO 221 box
//
// Copyright (c) Simon W. Moore 2023

block_size = 3;
// ////////////////////////////////////////////////
// Block dimensions in mm -- DO NOT EDIT
conwidth = 5.6; // width of a single conductor
condepth = 8.2;
// DO NOT EDIT
border = 1.75; // block transparent plastic border
// DO NOT EDIT
blockheight = 18.25;
// DO NOT EDIT
fudge = 0.2;

// Wall thickness
wallt = 0.4*4;

// ////////////////////////////////////////////////
// OpenSCAD special variables -- DO NOT EDIT
$fa = 1;
// DO NOT EDIT
$fs = 0.4;

// ////////////////////////////////////////////////
// Functions
function bw(x) = conwidth*x+border+fudge; // block width
function mw(i, n) = ( i==0 ? bw(blocks[i]) + 2 + mw(i+1, n) : (i < n ? bw(blocks[i]) + 2 + mw(i+1, n) : 0)); // mount width (index, max index)


module chamferCubeImpl(sizeX, sizeY, sizeZ, chamferHeight, chamferX, chamferY, chamferZ) {
    chamferX = (chamferX == undef) ? [1, 1, 1, 1] : chamferX;
    chamferY = (chamferY == undef) ? [1, 1, 1, 1] : chamferY;
    chamferZ = (chamferZ == undef) ? [1, 1, 1, 1] : chamferZ;
    chamferCLength = sqrt(chamferHeight * chamferHeight * 2);

    difference() {
        cube([sizeX, sizeY, sizeZ]);
        for(x = [0 : 3]) {
            chamferSide1 = min(x, 1) - floor(x / 3); // 0 1 1 0
            chamferSide2 = floor(x / 2); // 0 0 1 1
            if(chamferX[x]) {
                translate([-0.1, chamferSide1 * sizeY, -chamferHeight + chamferSide2 * sizeZ])
                rotate([45, 0, 0])
                cube([sizeX + 0.2, chamferCLength, chamferCLength]);
            }
            if(chamferY[x]) {
                translate([-chamferHeight + chamferSide2 * sizeX, -0.1, chamferSide1 * sizeZ])
                rotate([0, 45, 0])
                cube([chamferCLength, sizeY + 0.2, chamferCLength]);
            }
            if(chamferZ[x]) {
                translate([chamferSide1 * sizeX, -chamferHeight + chamferSide2 * sizeY, -0.1])
                rotate([0, 0, 45])
                cube([chamferCLength, chamferCLength, sizeZ + 0.2]);
            }
        }
    }
}



ziptiew=5;
ziptieh=2;
chamf=wallt*3/4;

w=bw(block_size);
d=condepth*2;
difference() {
  translate([-(w+wallt*2)/2,-(d+wallt*2)/2,0])
     chamferCubeImpl(w+wallt*2, d+wallt*2, blockheight+wallt*3+ziptieh, chamf);
  union() {
    translate([-w/2,-d/2,-1])
      color("red") cube([w, d, blockheight+wallt+1]);
    translate([-ziptiew/2,-(d+wallt*2+2)/2,blockheight+wallt*2])
      cube([ziptiew, d+wallt*2+2, ziptieh]);
  }
}

// add nobble wallt size
ystep=d/2;
for(y=[-ystep,ystep]) {
  translate([0,y,0])
    rotate([45,0,0])
      color("green") cube(wallt);
}
  